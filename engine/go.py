"""START BOT: the one start for the owner (the Start page's "Start trading" button, step_auto; START_BOT.bat in the console).

    python -X utf8 -m engine.go            # what START_BOT.bat runs
    python -X utf8 -m engine.go --dry-run  # say what it would do, change nothing

It first pulls the newest main (bot stopped only). Each step is skipped when it is already done, so the same double-click works the first time and every time after:
  1. account names: asked once (the 50K from data/autostart.json when it is there), kept in data/start_bot.json (gitignored)
  2. launch prep once (engine/launch_prep.py: allowlist both accounts, the 50K anchor, ATLAS on the 25K)
  3. the two Sim101 roundtrips, only until both have passed once (data/sim_roundtrip_last.json); needs the market open
  4. the owner types I ACCEPT LIVE RISK: nothing real is armed without that typed line (paper-only rule: the owner arms)
  5. NINJATRADER_LIVE=1 in .env.local.ps1; the bot server (scripts/run_bot.ps1) started, or restarted when that file is
     newer than the running supervisor (the file is read only when run_bot.ps1 starts)
  NinjaTrader is opened when it is not running; START BOT waits for its log-in (CONNECTED).
  After the start: auto-resume on the 50K (same typed phrase) and Startup-folder shortcuts for NinjaTrader and the bot
  server, so from then on turning the PC on (and NinjaTrader connecting) brings the bot back by itself.
  6. account B armed (second_model.json account_b "armed": true) and the bot started on the 50K (ATLAS trades the 25K
     through account_b), then the launch checklist
     printed and the dashboard opened

The same steps are the dashboard's Start page (web_next/js/next/start.js, engine/start_api.py, local PC only): step_nt,
step_prep, step_sims, step_arm are called by run() here and by the page (step_sims / step_arm in a detached job,
`python -m engine.go --step sims|arm`, because they may restart the server the page runs on). status() is the page's
checklist, accounts() / add_account() / remove_account() / set_anchor() / to_funded() its Accounts panel.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import threading
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "data", "start_bot.json")
AUTOSTART = os.path.join(ROOT, "data", "autostart.json")
ENV_FILE = os.path.join(ROOT, ".env.local.ps1")
SUP_PID = os.path.join(ROOT, "logs", "supervisor.pid")
RUN_BOT = os.path.join(ROOT, "scripts", "run_bot.ps1")
STOP_BOT = os.path.join(ROOT, "scripts", "stop_bot.ps1")
PORT = int(os.environ.get("PORT") or 8766)
BASE = f"http://127.0.0.1:{PORT}"
LIVE_LINE = '$env:NINJATRADER_LIVE = "1"'
LIVE_PHRASE = "I ACCEPT LIVE RISK"
FEED_FIX = "right-click the MNQ 5-minute chart > Reload NinjaScript (or re-add LE_BarFeed)"
# the files the Start page reads / writes; None = the module's own default (tests point them at temp copies)
SECOND_PATH = None       # second_model.json (account B = ATLAS's account)
ALLOW_PATH = None        # data/nt_accounts_allow.json
ACCOUNTS_PATH = None     # data/accounts.json (extra Zlarior accounts, funded accounts)
ANCHOR_PATH = None       # data/eval_anchor.json
JOB_FILE = os.path.join(ROOT, "logs", "start_job.json")       # the dashboard's running step (logs/ is gitignored)
JOB_LOG = os.path.join(ROOT, "logs", "start_job.log")
JOB_MAX_S = 1800
AUTO_MAX_S = 3 * 3600    # "Start trading" waits for NinjaTrader's log-in and the live bars
POPEN = None             # tests: a fake subprocess.Popen for job_start


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save(cfg, path=None):
    path = path or CFG
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=1)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, path)


def _http(path, body=None, timeout=5):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def server_up() -> bool:
    try:
        return bool(_http("/api/health/ping", timeout=3).get("ok"))
    except Exception:
        return False


def bot_running() -> bool:
    try:
        return bool(_http("/api/live/state").get("running"))
    except Exception:
        return False


def market_open(now=None) -> bool:
    """CME Globex: Sun 18:00 ET -> Fri 17:00 ET, closed 17:00-18:00 ET every weekday and on CME holidays (cme_calendar)."""
    from zoneinfo import ZoneInfo
    t = now or dt.datetime.now(ZoneInfo("America/New_York"))
    wd, h = t.weekday(), t.hour
    if wd == 5 or (wd == 6 and h < 18) or (wd == 4 and h >= 17):
        return False
    if h == 17:
        return False
    try:                                  # CME holiday closure / after an early halt (engine/cme_calendar.py)
        from .cme_calendar import halted
        return not halted((t if t.tzinfo else t.replace(tzinfo=ZoneInfo("America/New_York"))).timestamp())
    except Exception:
        return True


def session_day(now=None) -> str:
    """The trading session the next bar belongs to: from 18:00 ET it is the next weekday's (Sunday 21:00 -> Monday)."""
    from zoneinfo import ZoneInfo
    t = now or dt.datetime.now(ZoneInfo("America/New_York"))
    d = t.date() + dt.timedelta(days=1 if t.hour >= 18 else 0)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d.isoformat()


def ask(prompt, default=None, inp=input):
    s = (inp(f"{prompt}{f' [{default}]' if default else ''}: ") or "").strip()
    return s or (default or "")


def names(cfg, inp=input):
    """The 50K and 25K NinjaTrader account names, asked once and kept in data/start_bot.json."""
    lit = cfg.get("lit") or (_read(AUTOSTART).get("nt_account") or "").strip() or None
    if not cfg.get("lit"):
        lit = ask("50K account name exactly as NinjaTrader's Accounts tab shows it", lit, inp)
    atlas = cfg.get("atlas") or ask("25K account name exactly as NinjaTrader's Accounts tab shows it", None, inp)
    if not lit or not atlas or lit == atlas:
        return None
    cfg.update(lit=lit, atlas=atlas)
    return cfg


def mixup(lit, atlas, balances=None) -> str | None:
    """Why the two names look swapped or wrong (None = fine): a name that says the other size ("25K" in the 50K slot,
    "50K" in the 25K slot), a Sim account, or - when LE_BarFeed's accounts.csv is there - the NinjaTrader balance
    (the 50K above $35,000, the 25K below)."""
    from .ninjatrader import is_sim
    u, v = lit.upper().replace(" ", ""), atlas.upper().replace(" ", "")
    if is_sim(lit) or is_sim(atlas):
        return "a Sim account was typed: type the two MFFU accounts, not Sim101"
    if ("25K" in u and "50K" not in u) or ("50K" in v and "25K" not in v):
        return f"the names look swapped: {lit} reads like the 25K and/or {atlas} like the 50K"
    if balances is None:
        balances = nt_balances()
    return slot_problem(lit, "50K", balances) or slot_problem(atlas, "25K", balances)


def nt_balances() -> dict:
    """{NinjaTrader account Name: balance} from LE_BarFeed's accounts.csv, fresh rows only ({} when it is not there)."""
    try:
        from . import broker_balance
        return {n: r.get("netliq") or r.get("cash") for n, r in (broker_balance.read().get("rows") or {}).items() if r.get("fresh")}
    except Exception:
        return {}


def slot_problem(name, size, balances=None) -> str | None:
    """Why one account Name cannot be the 50K ("50K") or the 25K ("25K") slot (None = fine): a Sim account, a name that
    says the other size, or a NinjaTrader balance of the other size (50K above $35,000, 25K below)."""
    from .ninjatrader import is_sim
    name = str(name or "").strip()
    if not name or any(c in name for c in ";,\r\n|"):
        return "type the account Name exactly as NinjaTrader's Accounts tab shows it"
    if is_sim(name):
        return f"{name} is a Sim account: use the MFFU account, not Sim101"
    u, other = name.upper().replace(" ", ""), "25K" if size == "50K" else "50K"
    if other in u and size not in u:
        return f"{name} reads like a {other} account, not the {size}"
    bal = (nt_balances() if balances is None else balances).get(name)
    if bal is not None and (float(bal) < 35000) == (size == "50K"):
        return f"{name} has ${float(bal):,.0f} in NinjaTrader: that is not the {size}"
    return None


def route_problems(lit, atlas, state=None, b=None) -> dict:
    """After the start: who trades where, split in two (audit 2026-11-22 Package A: an unarmed ATLAS stopped Zlarior's 50K
    and the Start job retried every 60 s = the Re-arm loop).
      hard: the bot must be stopped (not running, Zlarior not on the 50K, the 25K also an extra, not NinjaTrader, ATLAS
            ARMED on another Name / plan: a double or wrong route).
      soft: said, never stopped: ATLAS's 25K not armed (its orders are refused by the live gate anyway), or an UNARMED
            ATLAS block on another Name / plan (it cannot trade)."""
    from . import second
    if state is None:
        try:
            state = _http("/api/live/state")
        except Exception as e:
            return {"hard": [f"bot state not readable ({e.__class__.__name__})"], "soft": []}
    b = second.load_cfg(SECOND_PATH).get("account_b") if b is None else b
    b = b or {}
    cfg = (state or {}).get("cfg") or {}
    hard, soft = [], []
    if not (state or {}).get("running"):
        hard.append("the bot is not running")
    if cfg.get("nt_account") != lit:
        hard.append(f"Zlarior is on {cfg.get('nt_account')!r}, not the 50K {lit!r}")
    for e in cfg.get("accounts") or []:                 # extra LIT accounts (data/accounts.json) must not include the 25K
        if isinstance(e, dict) and e.get("enabled", True) is not False and str(e.get("nt_account") or "") == atlas:
            hard.append(f"Zlarior also lists the 25K {atlas!r} as an extra account (data/accounts.json)")
    if cfg.get("adapter") != "ninjatrader":
        hard.append(f"the bot runs on {cfg.get('adapter')!r}, not NinjaTrader")
    armed = b.get("armed") is True
    side = hard if armed else soft
    if str(b.get("account") or "") != atlas:
        side.append(f"ATLAS is on {b.get('account')!r}, not the 25K {atlas!r}")
    elif not armed:
        soft.append("ATLAS's 25K is not armed")
    if str(b.get("plan") or "") != "builder25k":
        side.append(f"ATLAS plan is {b.get('plan')!r}, not builder25k")
    return {"hard": hard, "soft": soft}


def verify_routes(lit, atlas, state=None, b=None) -> list:
    """The HARD route problems only ([] = nothing that needs the bot stopped; see route_problems for the soft ones)."""
    return route_problems(lit, atlas, state, b)["hard"]


def soft_routes(lit, atlas, state=None, b=None) -> list:
    """The soft ones (ATLAS not armed): said on the page / console, never a stop, never a retry loop."""
    try:
        return route_problems(lit, atlas, state, b)["soft"]
    except Exception:
        return []


def sims_passed() -> dict:
    from . import launch_check
    r = launch_check.load_sim_result()
    return {k: bool((r.get(k) or {}).get("ok")) for k in ("roundtrip", "add")}


def env_has_live(path=None) -> bool:
    path = path or ENV_FILE
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return any(ln.strip().replace("'", '"') == LIVE_LINE for ln in fh)
    except OSError:
        return False


def add_env_live(path=None):
    path = path or ENV_FILE
    pre = ""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            pre = fh.read()
    except OSError:
        pass
    with open(path, "a", encoding="utf-8") as fh:
        if pre and not pre.endswith("\n"):
            fh.write("\r\n")
        fh.write(LIVE_LINE + "\r\n")


def env_newer_than_server(env=None, pid=None) -> bool:
    env, pid = env or ENV_FILE, pid or SUP_PID
    try:
        return os.path.getmtime(env) > os.path.getmtime(pid)
    except OSError:
        return False


def _ps(script, *args):
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, *args]


def start_server(wait_s=120) -> bool:
    # hidden window (owner 2026-10-27 "I don't wanna use powershell at all"): the dashboard is the bot's face
    ps = _ps(RUN_BOT)
    subprocess.Popen(["cmd", "/c", "start", "Liquidity Engine bot", "/min", *ps[:1], "-WindowStyle", "Hidden", *ps[1:]], cwd=ROOT)
    t0 = time.time()
    while time.time() - t0 < wait_s:
        time.sleep(2)
        if server_up():
            return True
    return False


def stop_server():
    subprocess.run(_ps(STOP_BOT, "-KeepAutostart"), cwd=ROOT)
    for _ in range(30):
        if not server_up():
            return True
        time.sleep(1)
    return False


def arm_b(atlas, path=None, selftest=None) -> dict:
    """second_model.json account_b "armed": true on the 25K (a real account B also needs it: engine/account_b.py). Called
    only after the owner typed the LIVE phrase; every other account_b field is kept."""
    from . import second, account_b
    path = path or SECOND_PATH
    ab = second.load_cfg(path).get("account_b") or {}
    if str(ab.get("account") or "").strip() != atlas:
        return {"ok": False, "error": f"account B is {ab.get('account')!r}, not the 25K {atlas!r}"}
    if ab.get("armed") is True:
        return {"ok": True, "already": True}
    keep = {k: v for k, v in ab.items() if k not in ("account", "plan", "eval_start", "strategies", "sizing")}
    return account_b.set_account_b(atlas, plan=ab.get("plan") or "builder25k", start=ab.get("eval_start"),
                                   sizing=ab.get("sizing") or "need", strategies=ab.get("strategies"), path=path,
                                   selftest=selftest, extra={**keep, "armed": True})


NT_EXE = os.environ.get("NINJATRADER_EXE") or r"C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe"


def nt_running() -> bool:
    if os.name != "nt":
        return False
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq NinjaTrader.exe", "/NH"], capture_output=True, text=True)
    return "NinjaTrader.exe" in (r.stdout or "")


def ensure_ninjatrader(wait_s=900, connected=None, sleep=time.sleep) -> bool:
    """NinjaTrader open (started here when it is not) and showing a CONNECTED connection; waits up to 15 min for the
    owner's NinjaTrader log-in. True = connected."""
    from . import autoresume
    connected = connected or (lambda: autoresume.nt_connected({"adapter": "ninjatrader"}))
    if connected() is True:
        return True
    if os.name == "nt" and not nt_running():
        if os.path.exists(NT_EXE):
            print("     opening NinjaTrader")
            subprocess.Popen([NT_EXE], cwd=os.path.dirname(NT_EXE))
        else:
            print(f"     NinjaTrader not found at {NT_EXE}: open it yourself")
    print("     Log in to NinjaTrader and connect your MFFU account (this window waits up to 15 minutes)")
    t0 = time.time()
    while time.time() - t0 < wait_s:
        sleep(5)
        if connected() is True:
            print("     NinjaTrader connected")
            return True
    return False


def feed_problem():
    """None = LE_BarFeed's MNQ 5m file is fresh (the NQ chart's with signal_root "NQ") and the chart is on the order
    contract; else why not (engine/ninjatrader.NinjaTraderBars.recent_bars; the roll line from engine/roll_watch.problem:
    the chart still on 12-26 after the Dec 10 roll, when the adapter sends no new entry)."""
    try:
        from .ninjatrader import NinjaTraderBars, default_folder
        df, why, _ = NinjaTraderBars(default_folder()).recent_bars("NQ", "5m", "1d")
        if df is None:
            return why or "no bars"
        from . import roll_watch
        return roll_watch.problem(default_folder())
    except Exception as e:
        return f"{e.__class__.__name__}: {e}"


def _roll_text(why) -> bool:
    """Is this feed problem the roll line? It carries its own fix (switch the chart's contract), not FEED_FIX."""
    try:
        from . import roll_watch
        return roll_watch.is_problem_text(why)
    except Exception:
        return False


def ensure_feed(wait_s=900, problem=None, sleep=time.sleep) -> bool:
    """The NinjaTrader bar feed fresh (the Sim test and every trade need it); shows the chart fix once and waits up to
    15 min for it. True = fresh."""
    problem = problem or feed_problem
    why = problem()
    if why is None:
        return True
    print(f"     The bot gets no live bars from NinjaTrader ({why}).")
    print("     Fix it in NinjaTrader now (this window waits and goes on by itself):")
    try:
        from .ninjatrader import nt_instrument
        inst = nt_instrument("MNQ")                     # the order contract today (MNQ 03-27 from Thu 2026-12-10)
    except Exception:
        inst = "MNQ 12-26"
    print(f"       1. Open the {inst} chart, set it to 5 Minute (or New > Chart: {inst}, Minute, 5).")
    print("       2. Right-click the chart > Indicators > LE_BarFeed > Add > OK (already listed? Remove it, Add it again).")
    t0 = time.time()
    while time.time() - t0 < wait_s:
        sleep(15)
        if problem() is None:
            print("     Live bars OK")
            return True
    return False


def startup_shortcuts():
    """Windows Startup folder (no admin): NinjaTrader and START_DASHBOARD.bat (the bot server; auto-resume then brings the
    bot back on the 50K and the 25K once NinjaTrader connects). Replaces the two it made before."""
    if os.name != "nt":
        return
    ps = ("$st=[Environment]::GetFolderPath('Startup'); $sh=New-Object -ComObject WScript.Shell; "
          f"$a=$sh.CreateShortcut((Join-Path $st 'LE bot server.lnk')); $a.TargetPath='{os.path.join(ROOT, 'START_DASHBOARD.bat')}'; "
          f"$a.WorkingDirectory='{ROOT}'; $a.WindowStyle=7; $a.Save(); "
          + (f"$n=$sh.CreateShortcut((Join-Path $st 'NinjaTrader 8 (Liquidity Engine).lnk')); $n.TargetPath='{NT_EXE}'; "
             f"$n.WorkingDirectory='{os.path.dirname(NT_EXE)}'; $n.Save()" if os.path.exists(NT_EXE) else ""))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)


def checklist_lines():
    try:
        r = _http("/api/dash/launch", timeout=10)
    except Exception as e:
        return [f"  (launch checklist not readable yet: {e.__class__.__name__})"], None
    items = r.get("items") or (r.get("launch") or {}).get("items") or []
    out, red = [], 0
    for it in items:
        ok = it.get("state") == "good"
        red += 0 if ok else 1
        out.append(f"  [{'OK' if ok else '..'}] {it.get('label')}: {it.get('detail')}")
    return out, red


PULL = None              # tests: a fake engine.autoupdate.pull


def update(py=sys.executable) -> bool:
    """The newest main (fast-forward only) while the bot is stopped: engine/autoupdate.pull, the same code as the
    auto-update and UPDATE.bat (ATLAS's account block moved out of second_model.json, files checked out from main by
    hand, a shallow history). True = new code arrived (START BOT re-runs itself, the Start page restarts the server)."""
    from . import autoupdate, generated_files, nogithub
    if nogithub.active() and autoupdate.source()["remote"] == "origin":
        # GitHub-free mode (tools/bat/BOTS_BACK.bat / tools/bat/GO_LIVE_EVAL.bat; the account is gone, 2026-11-08) with no backup source: no git
        # fetch at all. A fetch would only fail (a scary "git fetch failed" line, or a sign-in window); new code comes from
        # the code zip. With update_source.json (the backup repo, 2026-11-14) the pull below fetches the backup, never origin.
        print(" [OK] Update by git skipped (GitHub-free mode: new code comes from the code zip, UPDATE_FROM_ZIP.bat).")
        return False
    if generated_files.git_exe() == "git" and not shutil.which("git"):
        print(" [..] Update skipped (git not found); starting the version on this PC.")
        return False
    try:
        r = (PULL or autoupdate.pull)()
    except Exception as e:
        print(f" [..] Update skipped ({e.__class__.__name__}: {e}); starting the version on this PC.")
        return False
    if r.get("status") == "updated":
        print(f" [OK] {r.get('say')}")
        return True
    if r.get("status") != "up_to_date":
        print(f" [..] {r.get('say')}; starting the version on this PC.")
    return False


def shortcut():
    """The desktop icons (scripts/make_shortcuts.ps1: LE START + LE STOP BOT, Windows only; replaces the icons it made
    before)."""
    if os.name == "nt":
        subprocess.run(_ps(os.path.join(ROOT, "scripts", "make_shortcuts.ps1")), cwd=ROOT, capture_output=True)


SHORTCUTS_V = 2          # the icon set of scripts/make_shortcuts.ps1 (2 = LE START + LE STOP BOT, 2026-10-26)
SHORTCUTS_MARK = os.path.join(ROOT, "data", "shortcuts.json")     # gitignored


def ensure_shortcuts(run=None, mark=None, startup=None) -> dict:
    """At the server's start (after an update): the desktop icons and the Windows Startup-folder shortcuts (NinjaTrader,
    the bot server = START_DASHBOARD.bat, which opens the Start page) are made once per SHORTCUTS_V, so the PC gets the
    new icons without any click. Windows only (tests pass run). Never raises."""
    mark = mark or SHORTCUTS_MARK
    if os.name != "nt" and run is None:
        return {"ok": True, "skipped": "not Windows"}
    if _read(mark).get("v") == SHORTCUTS_V:
        return {"ok": True, "already": True}
    try:
        r = (run or subprocess.run)(_ps(os.path.join(ROOT, "scripts", "make_shortcuts.ps1")), cwd=ROOT, capture_output=True,
                                    text=True, timeout=120)
        if r.returncode != 0:
            return {"ok": False, "error": ((r.stdout or "") + (r.stderr or "")).strip()[-200:]}
        (startup or startup_shortcuts)()
        _save({"v": SHORTCUTS_V, "t": int(time.time())}, mark)
        return {"ok": True, "made": True}
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


# ------------------------------------------------------------------------------------------------ the steps
# Each step prints what it does (the console window, or the dashboard job's log) and returns 0 = done / 1 = stopped.
# run() below calls them in order for START BOT; the dashboard Start page calls the same functions (engine/start_api.py).

def step_prep(cfg, dry=False) -> int:
    """1. launch prep once (allowlist both, the 50K anchor, ATLAS on the 25K); cfg["prepped"] kept in data/start_bot.json."""
    if cfg.get("prepped"):
        print(f"\n 1/4 Accounts already set up ({cfg['prepped']})")
        return 0
    print("\n 1/4 Setting up both accounts (allowlist, 50K balance and floor, ATLAS on the 25K)")
    if dry:
        print("     (dry run: would run engine.launch_prep)")
        return 0
    from . import launch_prep
    if launch_prep.main(["--atlas", cfg["atlas"], "--lit", cfg["lit"], "--atlas-start", session_day()]):
        print(" [FIX] Setup failed (see above). Send Claude a photo of this window.")
        return 1
    cfg["prepped"] = dt.date.today().isoformat()
    _save(cfg)
    return 0


def step_nt(dry=False, wait=True) -> int:
    """NinjaTrader open and connected (everything after needs it). wait=False (dashboard): open it and return at once."""
    print("\n     NinjaTrader")
    if dry:
        return 0
    if wait:
        ok = ensure_ninjatrader()
    else:
        ok = ensure_ninjatrader(wait_s=0, sleep=lambda s: None)
    if not ok:
        print(" [FIX] NinjaTrader is not connected. Log in to NinjaTrader, then double-click START BOT again." if wait else
              "     NinjaTrader is not connected yet: log in to NinjaTrader and connect your MFFU account.")
        return 1
    return 0


def step_sims(py=sys.executable, dry=False, restart=False, cfg=None) -> int:
    """2. the two Sim101 roundtrips, until both passed once (the bot stopped: the server is stopped for it). A failed
    test is tried again with the order file written straight into incoming (--write-mode direct); when that passes,
    cfg["write_mode"] = "direct" is kept in data/start_bot.json and every start (console or dashboard) uses it.
    restart=True (dashboard job): the server is started again afterwards, so the page comes back."""
    cfg = _read(CFG) if cfg is None else cfg
    sp = sims_passed()
    if all(sp.values()):
        print("\n 2/4 Sim101 test already passed")
        return 0
    print("\n 2/4 NinjaTrader Sim101 test (a 1-micro test order on Sim101, about 1 minute)")
    if not market_open():
        print(" [WAIT] The market is closed (open Sun 18:00 ET - Fri 17:00 ET, not 17:00-18:00).")
        print("        Double-click START BOT again after it opens.")
        return 1
    if not dry and not ensure_feed():
        print(" [FIX] Still no live bars from the MNQ chart. Send Claude a photo of the chart and this window.")
        return 1
    stopped = False
    if server_up() and not dry:
        stop_server()                                       # the roundtrip needs the bot stopped
        stopped = True
    try:
        for kind, flag in (("roundtrip", "--sim-roundtrip"), ("add", "--sim-roundtrip-add")):
            if sp[kind]:
                continue
            if dry:
                print(f"     (dry run: would run engine.ninjatrader {flag})")
                continue
            wm = ["--write-mode", cfg["write_mode"]] if cfg.get("write_mode") else []
            rc = subprocess.run([py, "-X", "utf8", "-m", "engine.ninjatrader", flag, *wm], cwd=ROOT).returncode
            if rc and cfg.get("write_mode") != "direct":
                # NinjaTrader may not notice a file MOVED into incoming\ on some installs: try writing it there directly
                print("     Trying again with the order file written straight into NinjaTrader's folder")
                time.sleep(5)
                rc = subprocess.run([py, "-X", "utf8", "-m", "engine.ninjatrader", flag, "--write-mode", "direct"],
                                    cwd=ROOT).returncode
                if rc == 0:
                    cfg["write_mode"] = "direct"
                    _save(cfg)
                    print("     That works on this PC: the bot will always write its order files that way.")
            if rc:
                print(" [FIX] The Sim test failed. Nothing is armed. Close NinjaTrader, open it again, log in, then run START BOT")
                print("       again. Still failing: send Claude a photo of this window.")
                return 1
        if not dry:
            print("     Sim101 test passed")
        return 0
    finally:
        if restart and stopped and not server_up():
            print("     starting the bot server again")
            start_server()


def arm_problem(cfg) -> str | None:
    """Why the arm step cannot run now (None = it can): names, mix-up, Sim tests, a bot already running."""
    lit, atlas = cfg.get("lit"), cfg.get("atlas")
    if not lit or not atlas or lit == atlas:
        return "two different account names are needed (50K for Zlarior, 25K for ATLAS)"
    bad = mixup(lit, atlas)
    if bad:
        return bad
    if not all(sims_passed().values()):
        return "the Sim101 test has not passed yet"
    if bot_running():
        return "the bot is already running: stop it first (STOP BOT or Bot control), then start again"
    return None


LAST_ROWS = []           # the last START's per-account rows (engine/arm_report): the Start page's status line reads them
SELFTEST = None          # tests: a fake for engine.ninjatrader --selftest in the funded-name switch


def nt_account_names() -> list:
    """Every account Name NinjaTrader's Accounts tab lists, from LE_BarFeed's accounts.csv ([] when it is not there)."""
    try:
        return [r["name"] for r in nt_names()]
    except Exception:
        return []


def _atlas_fix(why):
    """A plain 'exact fix' for the reason ATLAS's arm failed (engine/arm_report: 'NOT ARMED: ATLAS 25K: <why> -> <fix>')."""
    w = str(why or "").lower()
    if "not in ninjatrader" in w or "not the 25k" in w or "switch" in w:
        return "START BOT again and type YES at the switch question; or Start page > Accounts > Funded"
    if "selftest" in w:
        return "close NinjaTrader, open it, log in, then START BOT again"
    return "send Claude a photo of this window"


def resolve_atlas(cfg, inp=None) -> str | None:
    """The eval -> funded rename (2026-11-22: MFFU renamed ATLAS's NinjaTrader account MFFUEV... -> MFFUSF..., the saved name
    stayed the eval's and ATLAS ended the START armed false). Called only after the owner typed the live phrase. When the saved
    ATLAS name is not in NinjaTrader's account list and exactly ONE account has the same plan family and last 4 digits, both
    names are SHOWN and the owner must type YES; only then the name moves (engine/account_b.to_funded, the funded switch;
    data/start_bot.json follows). Never silent, never without YES, never a guess. Returns None (fine / switched) or the plain
    reason ATLAS cannot be armed (a [FIX] line is printed)."""
    from . import arm_report, second
    atlas = str(cfg.get("atlas") or "").strip()
    bacc = str((second.load_cfg(SECOND_PATH).get("account_b") or {}).get("account") or "").strip()
    nt = nt_account_names()
    if not atlas or (bacc == atlas and (not nt or atlas in nt)):
        if atlas and atlas in nt:          # the old eval Name still listed next to its funded rename: say it, change nothing
            twin = arm_report.find_funded_candidates(atlas, nt, lambda n: role_of(n, cfg))
            if len(twin) == 1:
                print(f" [CHECK] ATLAS trades {atlas}, but NinjaTrader also lists {twin[0]} (the same account number, funded). "
                      "If MFFU moved ATLAS to that one: Start page > Accounts > Funded. Nothing changed.")
        return None
    if bacc == atlas:                       # the saved name is not in NinjaTrader's list any more
        bals = nt_balances()
        old, cands = atlas, [c for c in arm_report.find_funded_candidates(atlas, nt, lambda n: role_of(n, cfg))
                             if not slot_problem(c, "25K", bals)]
    elif bacc and atlas in nt and arm_report.renamed(bacc, atlas):   # the start config already holds the funded name, account B not
        old, cands = bacc, [atlas]
    else:
        return None                          # arm_b says its own plain reason
    if len(cands) != 1:
        why = (f"{old} is not in NinjaTrader's account list and no other account matches it (same plan, same last 4 digits)"
               if not cands else
               f"{old} is not in NinjaTrader's account list and {len(cands)} accounts could be its funded rename: "
               + ", ".join(cands))
        print(f" [FIX] ATLAS: {why}. Open NinjaTrader's Accounts tab, find the funded 25K, then Start page > Accounts > Funded. ATLAS is NOT armed.")
        return why
    new = cands[0]
    if bot_running():
        why = f"{old} is not in NinjaTrader; {new} looks like its funded rename, but the bot is running (a name switch needs it stopped)"
        print(" [FIX] ATLAS: the 25K name can only switch while the bot is stopped: STOP BOT, then START BOT and type YES. ATLAS is NOT armed.")
        return why
    print(f"\n ATLAS: the saved 25K name is NOT in NinjaTrader's account list.")
    print(f"        saved name (passed eval):  {old}")
    print(f"        NinjaTrader has (funded):  {new}   <- same plan, same last digits, the only match")
    if inp is None:
        why = f"{old} is not in NinjaTrader; {new} looks like its funded rename and needs your YES"
        print(f" [FIX] Run START_BOT.bat and type YES at the switch question (the Start page cannot ask it). ATLAS is NOT armed.")
        return why
    try:
        ans = ask(f" Type YES to switch ATLAS from {old} to {new} (anything else leaves ATLAS NOT armed)", None, inp)
    except (EOFError, KeyboardInterrupt, OSError):
        ans = ""                            # no console / piped stdin ran out: never a YES
    if str(ans or "").strip().upper() != "YES":
        print(" ATLAS name NOT switched.")
        return f"you did not type YES to switch {old} to {new}"
    bal = nt_balances().get(new)
    lit, _ = _names(cfg)
    r = (arm_b_switch(old, new, bal, lit))
    if not r.get("ok"):
        why = f"switching to {new} failed: {r.get('error')}"
        print(f" [FIX] {why}")
        return why
    cfg["atlas"] = new
    _save(cfg)
    if r.get("say"):
        print(f" {r['say']}")
    else:
        print(f" ATLAS name switched to the funded account {new}. Funded start balance "
              + (f"${float(bal):,.2f} (NinjaTrader)" if bal is not None else "= the plan start") + "; fix it on the Start page > Change balance if it differs.")
    return None


BAL_TOL = 50.0          # an eval switch takes NinjaTrader's balance as the funded start only within $50 of the plan start


def arm_b_switch(old, new, bal, lit) -> dict:
    """The name move after the owner's YES. ATLAS ALREADY FUNDED here (stage "funded": its funded start, start balance,
    payouts and the closed trades in its state file are real history): rename_funded() moves ONLY the Name and keeps every
    number (red team 2026-11-23: account_b.to_funded refuses an already-funded account, and any name change made the bot drop
    the state file, i.e. the funded profit, best day and consistency would restart at zero). A passed EVAL: the funded switch
    (account_b.to_funded), but only on a fresh funded balance (NinjaTrader within $50 of the plan start): later than that the
    funded account has history and the start day / balance must be typed on the Start page."""
    from . import account_b
    cur = account_b.raw_cfg(SECOND_PATH) or {}
    if str(cur.get("stage") or "eval").strip().lower() == "funded":
        return rename_funded(old, new, lit)
    try:
        from . import multi_account as MA
        plan = str(cur.get("plan") or "builder25k").lower().replace(" ", "").replace("_", "")
        start_bal = float(MA.rules_of({"preset": (account_b.PLANS.get(plan) or account_b.PLANS["builder25k"])["preset"]})["start"])
    except Exception:
        start_bal = None
    if bal is not None and start_bal is not None and abs(float(bal) - start_bal) > BAL_TOL:
        return {"ok": False, "error": f"NinjaTrader shows ${float(bal):,.2f} on {new}, not the fresh ${start_bal:,.0f}: the funded "
                                      "account already has history, so its first funded day and start balance must be typed on the "
                                      "Start page > Accounts > Funded (nothing switched)"}
    return account_b.to_funded(new, dt.date.today().isoformat(), bal, path=SECOND_PATH, allow_path=ALLOW_PATH,
                               lit_account=lit, selftest=SELFTEST)


def rename_funded(old, new, lit=None) -> dict:
    """ATLAS's funded account got a new NinjaTrader Name (same account): the local block keeps EVERY field (stage, funded
    start, funded start balance, payouts, eval account, plan, sizing, strategies) except the Name, which is DISARMED until
    arm_b (the typed phrase) arms it again; the state file (closes, ledger, open trade, held, lock) moves to the new Name
    (a copy of the old one is kept), so the funded tracker, best day and consistency carry on. Refused: not funded, not an
    eval->funded rename pair, Zlarior's own account, the NinjaTrader self-test failing, or any write failing (then nothing
    is changed). Returns {"ok", "error" | "say"}."""
    import json as _json
    import re as _re
    import shutil as _sh
    from . import account_b, arm_report, second
    path = SECOND_PATH
    cur = account_b.raw_cfg(path)
    if not isinstance(cur, dict) or str(cur.get("account") or "").strip() != str(old).strip():
        return {"ok": False, "error": f"ATLAS's saved account is not {old}: nothing switched"}
    if str(cur.get("stage") or "").strip().lower() != "funded":
        return {"ok": False, "error": "ATLAS is not funded here: use the funded switch"}
    if not arm_report.renamed(old, new):
        return {"ok": False, "error": f"{new} is not the funded rename of {old}: nothing switched"}
    if lit and str(new).strip() == str(lit).strip():
        return {"ok": False, "error": f"{new} is Zlarior's own account: nothing switched"}
    ok, line = (SELFTEST or second._selftest_ok)()
    if not ok:
        return {"ok": False, "error": f"engine.ninjatrader --selftest failed ({line}): ATLAS NOT switched"}
    blk = {k: v for k, v in cur.items() if k not in ("armed", "confirm")}
    blk.update(account=str(new).strip(), renamed_from=str(old).strip())
    sp = account_b.state_file(path)
    st = None
    try:
        with open(sp, encoding="utf-8") as fh:
            st = _json.load(fh)
    except FileNotFoundError:
        st = None
    except Exception as e:
        return {"ok": False, "error": f"ATLAS's state file could not be read ({e.__class__.__name__}): nothing switched"}
    if isinstance(st, dict) and st.get("account") == str(old).strip():
        try:
            _sh.copyfile(sp, os.path.splitext(sp)[0] + f".renamed_{_re.sub(r'[^A-Za-z0-9_-]', '_', str(old))}.json")
        except Exception as e:
            return {"ok": False, "error": f"ATLAS's state file could not be kept ({e.__class__.__name__}): nothing switched"}
    else:
        st = None                           # no file, or another account's: nothing to carry
    account_b.write_local(blk, path, why=f"Funded account renamed by MFFU: {old} -> {new} (every funded number kept).")
    if account_b.raw_cfg(path) != blk:
        account_b.write_local(cur, path, why="rename write check failed: put back")
        return {"ok": False, "error": "the account_b write check failed: ATLAS not switched (put back)"}
    if st is not None:
        try:
            tmp = sp + ".rename.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                _json.dump({**st, "account": str(new).strip()}, fh, default=str)
            from . import fsutil as _fsutil
            _fsutil.replace(tmp, sp)
        except Exception as e:
            account_b.write_local(cur, path, why="state carry-over failed: put back")
            return {"ok": False, "error": f"ATLAS's state could not move to {new} ({e.__class__.__name__}): not switched (put back)"}
    try:
        from .ninjatrader import allow_account
        allow_account(str(new).strip(), path=ALLOW_PATH)
    except Exception:
        pass
    return {"ok": True, "say": f"ATLAS's funded account is now {new}; funded start, balance, payouts and trades kept."}


def _all_down(rows, z_lbl, why, fix):
    """The bot did not start / was stopped: no account trades, whatever the files say. Keeps the account's own reason first."""
    from . import arm_report as AR
    out = [AR.row(z_lbl, False, why, fix)]
    for r in rows:
        out.append(r if not r["armed"] else AR.row(r["label"], False, f"armed in the files, but {why}", fix))
    return out


def _summary(rows, rc):
    """The loud end of every START: one line per account + the 'NOT TRADING' banner, and data/arm_status.json for the phone."""
    from . import arm_report
    global LAST_ROWS
    LAST_ROWS = list(rows)
    print("\n ---- WHAT HAPPENED ----")
    for ln in arm_report.lines(rows):
        print(" " + ln if ln else "")
    arm_report.save(rows, path=_arm_status_path())
    return rc


def _arm_status_path():
    """data/arm_status.json for the real START; next to the config a test pointed this module at (SECOND_PATH / CFG in a temp
    folder) otherwise, so a test run never rewrites the phone's live armed status (night-hermetic 2026-11-23: a suite's
    leftover made the Brain glance say "not armed")."""
    from . import arm_report
    if os.path.normcase(os.path.realpath(arm_report.PATH)) != os.path.normcase(os.path.realpath(os.path.join(ROOT, "data", "arm_status.json"))):
        return arm_report.PATH                       # a test pointed arm_report itself somewhere: that wins
    for p, real in ((SECOND_PATH, None), (CFG, os.path.join(ROOT, "data", "start_bot.json"))):
        if p and (real is None or os.path.normcase(os.path.realpath(p)) != os.path.normcase(os.path.realpath(real))):
            return os.path.join(os.path.dirname(p), "arm_status.json")
    return arm_report.PATH


def step_arm(cfg, phrase, dry=False, open_page=True, inp=None) -> int:
    """step 4 (_step_arm) with the loud summary also on an error (red team 2026-11-23): bot not running = every account NOT
    ARMED with the error as the reason; bot running = one [CHECK] line (the summary never guesses ARMED). Re-raises."""
    try:
        return _step_arm(cfg, phrase, dry=dry, open_page=open_page, inp=inp)
    except Exception as e:
        if phrase == LIVE_PHRASE and not dry:
            why = f"START stopped by an error ({e.__class__.__name__})"
            try:
                up = bot_running()
            except Exception:
                up = False
            if up:
                print(f"\n [CHECK] {why} after the bot started: open the Start page to see which accounts are armed.")
            else:
                from . import arm_report as AR
                _summary([AR.row("Zlarior 50K", False, why, "send Claude a photo of this window"),
                          AR.row("ATLAS 25K", False, why, "send Claude a photo of this window")], 1)
        raise


def _step_arm(cfg, phrase, dry=False, open_page=True, inp=None) -> int:
    """4. only with the typed phrase: NINJATRADER_LIVE in .env.local.ps1, the server (re)started so it reads it, the 25K
    armed, the bot started on the 50K, the routes checked in the running bot (stopped when wrong), auto-resume on, the
    Startup-folder shortcuts, then the launch checklist."""
    from . import arm_report as AR
    z_lbl, a_lbl = "Zlarior 50K", "ATLAS 25K"
    if phrase != LIVE_PHRASE:
        print(" Stopped. Nothing is armed.")
        why, fix = "the live phrase was not typed", "START BOT again and type I ACCEPT LIVE RISK yourself"
        return _summary([AR.row(z_lbl, False, why, fix), AR.row(a_lbl, False, why, fix)], 1) if not dry else 1
    print("\n 4/4 Starting the bot")
    if dry:
        print("     (dry run: would set NINJATRADER_LIVE, start the server, start the bot)")
        return 0
    bad = arm_problem(cfg)
    if bad:
        print(f" [FIX] {bad}. Nothing is armed.")
        return _summary([AR.row(z_lbl, False, bad, "do the [FIX] above, then START BOT again"),
                         AR.row(a_lbl, False, bad, "do the [FIX] above, then START BOT again")], 1)
    # every account is armed BEFORE any server (re)start below (2026-11-21 Rapid arm bug): a fresh server resumes the bot
    # from its autostart record at boot (server.py _autostart_resume) and the bot reads these files then
    rows = []
    why_name = resolve_atlas(cfg, inp)       # the eval -> funded rename: both names shown, the owner types YES (or a plain [FIX])
    if why_name:
        rb = {"ok": False, "error": why_name}
    else:
        rb = arm_b(cfg["atlas"])
    print(f"     25K (ATLAS): {'armed' if rb.get('ok') else 'NOT armed: ' + str(rb.get('error'))[:160]}")
    rows.append(AR.row(a_lbl, rb.get("ok"), rb.get("error"), _atlas_fix(rb.get("error"))))
    try:                                   # the Rapid EOD (engine/rapid.py): armed only here, after the typed phrase
        from . import rapid
        rr = rapid.arm(phrase)
        if not rr.get("off"):
            lbl = rapid.plan_info(rapid.read() or {})["label"]        # "Rapid EOD 25K" / "Rapid EOD 50K": the size shows here too
            print(f"     {lbl} (LIT + ATLAS): {'armed ' + str(rr.get('account')) if rr.get('ok') else 'NOT armed: ' + str(rr.get('error'))[:160]}")
            rows.append(AR.row(f"{lbl} (LIT + ATLAS)", rr.get("ok"), rr.get("error"), "send Claude a photo of this window"))
    except Exception as e:
        print(f"     Rapid EOD: NOT armed ({e.__class__.__name__}: {e})")
        rows.append(AR.row("Rapid EOD", False, f"{e.__class__.__name__}: {e}", "send Claude a photo of this window"))
    try:                                   # accounts added with engine.accounts (engine/account_cli.py): armed only here
        from . import account_cli
        for ln in account_cli.arm(phrase):
            print(f"     {ln}")
            if ln.startswith("Added accounts armed:"):
                rows += [AR.row(n.strip(), True) for n in ln.split(":", 1)[1].split(",") if n.strip()]
            elif "NOT armed" in ln:
                rows.append(AR.row(ln.split(":")[0][:60], False, ln, "send Claude a photo of this window"))
    except Exception as e:
        print(f"     Added accounts: NOT armed ({e.__class__.__name__}: {e})")
        rows.append(AR.row("Added accounts", False, f"{e.__class__.__name__}: {e}", "send Claude a photo of this window"))
    added = False
    if not env_has_live():
        add_env_live()
        added = True
    stale = server_up() and server_stale()
    if server_up() and (added or env_newer_than_server() or stale):
        print("     restarting the bot server so it runs the new version" if stale and not added else
              "     restarting the bot server so it reads the live switch")
        stop_server()
    if not server_up() and not start_server():
        print(' [FIX] The server did not start in 2 minutes. Double-click HEALTH_CHECK.bat (the server runs hidden).')
        return _summary(_all_down(rows, z_lbl, "the bot server did not start", "double-click HEALTH_CHECK.bat"), 1)
    from . import ninjatrader
    wm = ["--write-mode", cfg["write_mode"]] if cfg.get("write_mode") else []
    start = ["--start", "--account", cfg["lit"], "--confirm", phrase, *wm]
    if bot_running():                      # the (re)started server resumed the bot by itself, without the phrase: restarted
        print("     the bot server resumed the bot by itself: restarting it so every account armed above joins")
        ninjatrader.main(["--stop"])
    rc = ninjatrader.main(start)
    if rc and bot_running():               # its own resume won the race (it waits for NinjaTrader): once more, with the phrase
        print("     the bot server resumed the bot by itself meanwhile: restarting it once with the phrase")
        ninjatrader.main(["--stop"])
        rc = ninjatrader.main(start)
    if rc:
        print(" [FIX] The bot did not start (see the lines above). Send Claude a photo of this window.")
        return _summary(_all_down(rows, z_lbl, "the bot did not start", "send Claude a photo of this window"), 1)
    probs = verify_routes(cfg["lit"], cfg["atlas"])
    if probs:
        print(" [STOP] Wrong account set-up: " + "; ".join(probs) + ". Stopping the bot (nothing traded).")
        ninjatrader.main(["--stop"])
        return _summary(_all_down(rows, z_lbl, "the bot was stopped: " + "; ".join(probs)[:120], "fix the first NOT ARMED line, then START BOT again"), 1)
    soft = soft_routes(cfg["lit"], cfg["atlas"])
    if soft:                               # an unarmed ATLAS never stops Zlarior's 50K (audit Package A)
        print(f"\n [OK] Running Zlarior on the 50K {cfg['lit']}; ATLAS NOT armed: {'; '.join(soft)} (checked in the running bot)")
    else:
        print(f"\n [OK] Zlarior trades the 50K {cfg['lit']} · ATLAS trades the 25K {cfg['atlas']} (checked in the running bot)")
    ninjatrader.main(["--enable-auto-resume", "--account", cfg["lit"], "--confirm", phrase, *wm])
    try:                                   # and each armed account added with engine.accounts resumes with it
        from . import account_cli
        for ln in account_cli.resume_optin(phrase):
            print(f"     {ln}")
    except Exception:
        pass
    startup_shortcuts()
    print("\n Launch checklist (the bot unlocks entries by itself once everything reconciles):")
    lines, red = [], None
    for _ in range(9):                                     # up to ~90 s for the startup reconcile
        time.sleep(10)
        lines, red = checklist_lines()
        if red == 0:
            break
    print("\n".join(lines))
    print("\n [OK] Running. Leave the PC on, plugged in, NinjaTrader open. First trades from 02:00 ET." if red == 0 else
          "\n [..] Running; lines with .. are still settling or need the fix shown on the dashboard.")
    if open_page:
        _open()
    shortcut()
    keepalive_consent(phrase)              # the same typed phrase: keep-alive ON for exactly the accounts armed above
    return _summary([AR.row(z_lbl, True)] + rows, 0)


def armed_accounts(main_on=True) -> list:
    """[(keep-alive key, label, NinjaTrader Name)] of every real MFFU account armed right now (after step_arm armed them):
    the 50K (main_on: the bot runs on it), ATLAS's 25K, the Rapid slots and the engine.accounts rows with "armed": true.
    Sim names are dropped by keepalive.start_consent; BLITZ (paper, hidden) and other firms are never listed. Never raises."""
    out = []
    try:
        from . import account_cli
        for r in account_cli.inventory():
            role, name = r.get("role"), str(r.get("name") or "").strip()
            if not name or r.get("sim") or r.get("mffu") is False or r.get("enabled", True) is False:
                continue
            if role == "main":
                if not main_on:
                    continue
                key, lbl = "lit", "Zlarior 50K"
            elif role == "b" and r.get("armed") is True:
                key, lbl = "atlas", "ATLAS 25K"
            elif role == "rapid" and r.get("armed") is True:
                # night-k7proof 2026-11-23: the slot is the key (engine/keepalive PRIORITY / lanes: "rapid" or "rapid2"). Before,
                # both slots were keyed "rapid": start_consent skipped the 2nd as a duplicate and the 2nd Rapid (the Rapid EOD 50K)
                # never got the keep-alive from the START phrase
                key = "rapid2" if r.get("id") == "rapid2" else "rapid"
                lbl = account_cli.PLANS.get(r.get("plan"), {}).get("label") or "Rapid EOD"
            elif role == "extra" and r.get("armed") is True and r.get("id"):
                key, lbl = f"x:{r['id']}", account_cli.PLANS.get(r.get("plan"), {}).get("label") or "added account"
            else:
                continue
            out.append((key, f"{lbl} ..{name[-4:]}", name))
    except Exception:
        pass
    return out


def _ka_path() -> str:
    """data/keepalive.json next to the start config (CFG): the owner's real file on the PC, a temp copy in every test harness
    that points CFG at a temp folder (a test never turns a real keep-alive on)."""
    return os.path.join(os.path.dirname(CFG), "keepalive.json")


def keepalive_consent(phrase, main_on=True) -> str:
    """The START phrase also switches the MFFU 7-day keep-alive ON for exactly the accounts it armed (engine/keepalive
    start_consent; owner 2026-11-22). Prints and returns the one summary line. Never raises."""
    try:
        from . import keepalive
        r = keepalive.start_consent(phrase, armed_accounts(main_on), path=_ka_path())
        line = r.get("line") or ""
    except Exception as e:
        line = f"Keep-alive NOT changed ({e.__class__.__name__}): KEEPALIVE_ON.bat turns it on."
    if line:
        print(f"\n [OK] {line}" if line.startswith("Keep-alive ON") else f"\n [..] {line}")
    return line


def keepalive_missing() -> list:
    """Labels of the armed real accounts whose keep-alive is not ON yet and not switched OFF by the owner (the bot already
    runs: START offers the phrase once for them). Never raises."""
    try:
        from . import keepalive
        C = keepalive.load_config(None, path=_ka_path())
        off = C.get("owner_off") or {}
        from .ninjatrader import is_sim
        return [lbl for k, lbl, n in armed_accounts() if not is_sim(n) and C["accounts"].get(k) is not True
                and k not in off and "*" not in off]
    except Exception:
        return []


def migrate():
    """ATLAS's account block out of the tracked second_model.json (engine/account_b.migrate_local); prints what it did."""
    try:
        from . import account_b
        m = account_b.migrate_local()
        if m.get("status") in ("migrated", "error"):
            print(f" [{'OK' if m['status'] == 'migrated' else '..'}] {m.get('say')}")
        return m
    except Exception as e:
        return {"status": "error", "say": f"{e.__class__.__name__}: {e}"}


def head_sha():
    from . import generated_files
    c, out = generated_files._git("rev-parse", "HEAD", cwd=ROOT, timeout=30)
    s = out.strip()
    return s if c == 0 and len(s) == 40 else None


def server_stale() -> bool:
    """The bot server runs older code than this folder (an update arrived after it started; an older server has no
    /api/next/start/boot): it is started again before the bot starts, so the bot never runs the old code (an old
    server would read ATLAS's account from second_model.json, which the update emptied)."""
    if not server_up():
        return False
    head = head_sha()
    if not head:
        return False
    try:
        return _http("/api/next/start/boot").get("sha") != head
    except Exception:
        return True


def run(dry=False, inp=input, py=sys.executable, pull=True) -> int:
    print("\n ==== Zlarior + ATLAS: START BOT ====\n")
    if not dry and not bot_running():
        migrate()
    if pull and not dry and not bot_running() and update(py):
        print(" Updated to the newest version: restarting START BOT.")
        return subprocess.run([py, "-X", "utf8", "-m", "engine.go", "--no-pull"], cwd=ROOT).returncode
    cfg = _read(CFG)
    if not names(cfg, inp):
        print(" [FIX] Two different account names are needed. Double-click START BOT again.")
        return 1
    bad = mixup(cfg["lit"], cfg["atlas"])
    if bad:
        print(f" [FIX] {bad}.")
        print("       Nothing changed. Double-click START BOT again and type the names from NinjaTrader's Accounts tab.")
        if not dry:
            for k in ("lit", "atlas", "prepped"):
                cfg.pop(k, None)
            _save(cfg)
        return 1
    if not dry:
        _save(cfg)
    print(f" 50K (Zlarior): {cfg['lit']}    25K (ATLAS): {cfg['atlas']}")

    if bot_running():
        print("\n [OK] The bot is already running. Nothing changed. Opening the dashboard.")
        miss = [] if dry else keepalive_missing()
        if miss:                           # the bot came back by itself (auto-resume): the keep-alive still needs his phrase
            print(f"\n MFFU 7-day keep-alive is not on yet for: {', '.join(miss)}.")
            print(f"     It places ONE 1-MNQ trade on an account only when it would otherwise hit 7 days without a trade")
            print(f"     (about -$2.40, at most -$22.90). Off any time: tools/bat/KEEPALIVE_OFF.bat.")
            try:
                p = typed_phrase(ask(" Type  I ACCEPT LIVE RISK  to switch it on (Enter = leave it off)", "", inp))
            except (EOFError, KeyboardInterrupt, OSError):
                p = ""                     # no console / piped stdin ran out: left off
            if p == LIVE_PHRASE:
                keepalive_consent(p)
            else:
                print("     Keep-alive left as it was.")
        if not dry:
            _open()
        return 0
    if step_prep(cfg, dry):
        return 1
    if step_nt(dry):
        return 1
    if step_sims(py, dry, cfg=cfg):
        return 1

    # 3. the owner arms (typed, never by the bot)
    print("\n 3/4 Real money:")
    print(f"       Zlarior (LIT)  ->  50K  {cfg['lit']}")
    print(f"       ATLAS          ->  25K  {cfg['atlas']}")
    for ln in phrase_also_arms():
        print(ln)
    print("     Check each name against NinjaTrader's Accounts tab (the phrase arms every account listed here).")
    print("     Typing the line also lets the bot come back by itself after a restart (PC on + NinjaTrader connected);")
    print("     STOP BOT keeps it stopped until you start it again; the kill switch turns that off for good.")
    print("     It also turns the MFFU 7-day keep-alive ON for these accounts: one 1-MNQ trade (about -$2.40, at most -$22.90)")
    print("     only when an account would otherwise hit 7 days without a trade. Off any time: tools/bat/KEEPALIVE_OFF.bat.")
    phrase = typed_phrase(ask(" Type  I ACCEPT LIVE RISK  then Enter (anything else stops here, nothing armed)", None, inp))
    return step_arm(cfg, phrase, dry, inp=inp)


def phrase_also_arms() -> list:
    """START BOT step 3: every OTHER account the typed phrase arms (added with ADD_ACCOUNT.bat: a Builder 25K #2, the Rapid EOD
    25K / 50K), one line each, so the owner checks every Name before he types it (2026-11-20 night-rapidready: the window
    listed only the 50K and the 25K while the phrase also armed the 25K #2 and the Rapid). Print only; never raises."""
    out = []
    try:
        from . import account_cli
        for r in account_cli.inventory():
            if r.get("role") not in ("extra", "rapid") or r.get("enabled", True) is False:
                continue
            if r["role"] == "extra" and not (r.get("cli") or r.get("armed")):
                continue                     # an old multi_account row the phrase does not arm (and not armed): not trading
            plan = account_cli.PLANS.get(r.get("plan"), {}).get("label", str(r.get("plan") or ""))
            who = {"lit": "Zlarior (LIT)", "lit+atlas": "Zlarior + ATLAS", "atlas": "ATLAS"}.get(r.get("bots"), str(r.get("bots")))
            out.append(f"       {who + ('  ' if len(who) < 15 else ' ')}->  {plan}{' funded' if r.get('stage') == 'funded' else ''}  {r['name']}"
                       + (" (Sim)" if r.get("sim") else ""))
    except Exception:
        pass
    return out


def typed_phrase(s) -> str:
    """The owner's typed line: capitals and extra spaces do not matter ("i accept live risk" counts); anything else is
    passed on unchanged (and refused)."""
    s = str(s or "")
    return LIVE_PHRASE if " ".join(s.split()).upper() == LIVE_PHRASE else s


# ------------------------------------------------------------------------------------------------ dashboard Start page
# The checklist, the account panel and the step jobs of the PC dashboard's Start page (engine/start_api.py serves them,
# local PC only). Every change goes through the step functions above or the modules START BOT already uses.
PLANS = {"builder50k": ("mffu_builder_50k", "MFFU Builder 50K", "50K"), "builder25k": ("mffu_builder_25k", "MFFU Builder 25K", "25K")}
_QUIET = threading.Lock()


def _quiet(fn, *a, **k):
    """fn(*a, **k) with its printed lines captured for the page: (result, lines)."""
    import contextlib
    import io
    buf = io.StringIO()
    with _QUIET, contextlib.redirect_stdout(buf):
        try:
            r = fn(*a, **k)
        except Exception as e:
            print(f" [FIX] {e.__class__.__name__}: {e}")
            r = 1
    return r, [ln.rstrip() for ln in buf.getvalue().splitlines() if ln.strip()]


def _b() -> dict:
    from . import account_b
    return account_b.raw_cfg(SECOND_PATH) or {}


def _allowed() -> set:
    from .ninjatrader import allowed_accounts
    return allowed_accounts(ALLOW_PATH)


def _allow(name, remove=False):
    from .ninjatrader import allow_account
    return allow_account(name, path=ALLOW_PATH, remove=remove)


def _accounts_path() -> str:
    from . import multi_account as ma
    return ACCOUNTS_PATH or ma.ACCOUNTS_PATH


def _extras() -> list:
    from . import multi_account as ma
    return ma.load_file(_accounts_path())


def _state():
    try:
        return _http("/api/live/state")
    except Exception:
        return None


def _names(cfg=None) -> tuple:
    cfg = _read(CFG) if cfg is None else cfg
    return str(cfg.get("lit") or "").strip(), str(cfg.get("atlas") or "").strip()


def role_of(name, cfg=None, b=None, extras=None) -> str | None:
    """Which bot already trades this NinjaTrader account (None = free): one account is Zlarior's or ATLAS's, never both."""
    name = str(name or "").strip()
    if not name:
        return None
    lit, atlas = _names(cfg)
    b = _b() if b is None else b
    if name == lit:
        return "Zlarior's 50K"
    if name in (atlas, str(b.get("account") or "").strip()):
        return "ATLAS's 25K"
    if name == str(_c().get("account") or "").strip():
        return "BLITZ's 25K"
    for e in (_extras() if extras is None else extras):
        if str(e.get("nt_account") or "").strip() == name:
            return f"the funded account {e.get('id')}" if e.get("mode") == "funded" else f"the extra Zlarior account {e.get('id')}"
    try:                                   # the Rapid EOD slots (data/rapid.json, rapid2.json; audit Package A: the Start page
        from . import rapid               # offered the armed Rapid as "New account", and its Name could go to ATLAS / an extra)
        for sl in rapid.SLOTS:
            blk = rapid.read(rapid.slot_path(sl))
            if blk and str(blk.get("account") or "").strip() == name:
                return "the Rapid EOD" + (" #2" if sl == "rapid2" else "")
    except Exception:                      # a broken rapid.json never crashes START
        pass
    return None


def set_names(lit, atlas) -> dict:
    """The Start page's "Accounts set" line: the 50K (Zlarior) and the 25K (ATLAS) Names, with START BOT's mix-up checks.
    A new pair clears "prepped" (the setup runs again for it)."""
    lit, atlas = str(lit or "").strip(), str(atlas or "").strip()
    if not lit or not atlas:
        return {"ok": False, "error": "Two account names are needed: the 50K for Zlarior and the 25K for ATLAS."}
    if lit == atlas:
        return {"ok": False, "error": "One account cannot be both Zlarior's and ATLAS's: pick two different accounts."}
    bad = mixup(lit, atlas)
    if bad:
        return {"ok": False, "error": f"Not saved: {bad}."}
    for n in (lit, atlas):
        e = next((e for e in _extras() if str(e.get("nt_account") or "").strip() == n), None)
        if e:
            return {"ok": False, "error": f"Not saved: {n} is already the account {e.get('id')} (remove it in Accounts first)."}
        who = role_of(n, cfg={}, b={}, extras=[])          # only the Rapid / BLITZ slots here (Zlarior / ATLAS are being set)
        if who and who.startswith("the Rapid EOD"):
            return {"ok": False, "error": f"Not saved: {n} is already {who} (one account, one route: remove it there first)."}
    if bot_running():
        return {"ok": False, "error": "Stop the bot first: it reads the accounts when it starts."}
    cfg = _read(CFG)
    changed = _names(cfg) != (lit, atlas)
    cfg.update(lit=lit, atlas=atlas)
    if changed:
        cfg.pop("prepped", None)
    _save(cfg)
    return {"ok": True, "changed": changed, "say": f"Zlarior → 50K {lit} · ATLAS → 25K {atlas}"}


def open_nt() -> dict:
    """The "NinjaTrader connected" line's button: open NinjaTrader when it is not running (no wait)."""
    rc, lines = _quiet(step_nt, False, False)
    return {"ok": True, "connected": rc == 0, "lines": lines}


def run_setup() -> dict:
    """The "Setup done" line's button: the launch prep (step_prep) again for the two saved names."""
    cfg = _read(CFG)
    lit, atlas = _names(cfg)
    if not lit or not atlas:
        return {"ok": False, "error": "Set the two account names first."}
    bad = mixup(lit, atlas)
    if bad:
        return {"ok": False, "error": f"{bad}."}
    if bot_running():
        return {"ok": False, "error": "Stop the bot first: the setup changes what it trades."}
    cfg.pop("prepped", None)
    rc, lines = _quiet(step_prep, cfg)
    return {"ok": rc == 0, "lines": lines, **({} if rc == 0 else {"error": "Setup failed: see the lines below."})}


def setup_missing(cfg=None, b=None, allow=None) -> list:
    """What the setup step still has to do for the saved names ([] = done): run once, both names allowlisted, ATLAS on
    the 25K."""
    cfg = _read(CFG) if cfg is None else cfg
    lit, atlas = _names(cfg)
    b = _b() if b is None else b
    allow = _allowed() if allow is None else allow
    miss = [] if cfg.get("prepped") else ["not run yet"]
    miss += [f"{n} is not on the allowlist" for n in (lit, atlas) if n not in allow]
    b_on = str(b.get("account") or "").strip()
    if b_on != atlas:
        miss.append(f"ATLAS is on {b_on or 'no account'}, not {atlas}")
    return miss


def status(state=None, connected=None, feed=None) -> dict:
    """The Start page checklist: one line per step, done or not, the one button that does it and the plain status line."""
    cfg = _read(CFG)
    lit, atlas = _names(cfg)
    b = _b()
    allow, sp, live = _allowed(), sims_passed(), env_has_live()
    st = _state() if state is None else state
    running = bool((st or {}).get("running"))
    if connected is None:
        from . import autoresume
        nt = autoresume.nt_connected({"adapter": "ninjatrader"})
    else:
        nt = connected()
    bars = feed_problem() if feed is None else feed()
    names_bad = None if (lit and atlas and lit != atlas) else "not set"
    if not names_bad:
        names_bad = mixup(lit, atlas)
    b_on = str(b.get("account") or "").strip()
    miss = setup_missing(cfg, b, allow) if not names_bad else ["set the account names first"]
    armed_b = bool(atlas) and b_on == atlas and b.get("armed") is True
    probs = verify_routes(lit, atlas, state=st or {}, b=b) if running and not names_bad else []
    sims_ok = all(sp.values())
    arm_miss = ([] if live else ["live switch off"]) + ([] if armed_b else ["25K not armed"])
    new = unarmed_added()                  # a Rapid / an engine.accounts row added DISARMED: red until the phrase arms it
    arm_txt = "; ".join(arm_miss + [f"{x} not armed" for x in new])
    run_bad = running and (probs or names_bad)
    steps = [
        {"key": "nt", "label": "NinjaTrader connected", "done": nt is True, "action": "nt", "button": "Open NinjaTrader",
         "needs": [], "detail": "connected" if nt is True else
         "not connected: log in to NinjaTrader and connect your MFFU account" if nt is False else
         "not seen: open NinjaTrader and log in"},
        {"key": "feed", "label": "Live bars from NinjaTrader", "done": bars is None, "action": "recheck", "button": "Check again",
         "needs": [], "detail": "LE_BarFeed's MNQ 5-minute bars are fresh" if bars is None else
         (bars if _roll_text(bars) else f"{bars}: {FEED_FIX}")},
        {"key": "accounts", "label": "Accounts set (50K → Zlarior, 25K → ATLAS)", "done": not names_bad, "action": "names",
         "button": "Set the names", "needs": [],
         "detail": f"Zlarior → 50K {lit} · ATLAS → 25K {atlas}" if not names_bad else
         ("pick the two accounts" if names_bad == "not set" else names_bad)},
        {"key": "setup", "label": "Setup done", "done": not miss, "action": "setup", "button": "Run setup", "needs": ["accounts"],
         "detail": f"allowlist, 50K balance and floor, ATLAS on the 25K ({cfg.get('prepped')})" if not miss else "; ".join(miss)},
        {"key": "sims", "label": "Sim tests passed", "done": sims_ok, "action": "sims", "button": "Run the Sim test",
         "needs": ["nt", "feed"], "detail": "both Sim101 roundtrips passed" if sims_ok else
         "a 1-micro test order on Sim101, about 1 minute, market open only"
         + ("" if market_open() else " (the market is closed now)")},
        {"key": "armed", "label": "Armed", "done": not arm_txt, "action": "arm", "button": "Arm and start",
         "needs": ["nt", "feed", "accounts", "setup", "sims"],
         "detail": "live switch on, 25K armed" if not arm_txt else arm_txt + (
             " (stop the bot, then Start trading and type I ACCEPT LIVE RISK)" if running else " (you type I ACCEPT LIVE RISK)")},
        {"key": "running", "label": "Running and routes verified", "done": bool(running and not probs and not names_bad),
         "action": "stop" if run_bad else "arm", "button": "Stop the bot" if run_bad else "Start",
         "needs": [] if run_bad else ["nt", "feed", "accounts", "setup", "sims"],
         "detail": "Zlarior on the 50K, ATLAS on the 25K (checked in the running bot)" if running and not run_bad
         else ("; ".join(probs) or "check the account names") if running else "stopped"},
    ]
    done = {s["key"]: s["done"] for s in steps}
    for s in steps:
        s["ready"] = all(done[k] for k in s["needs"])
        s["first"] = next((x["label"] for x in steps if x["key"] in s["needs"] and not x["done"]), None)
    say = " · ".join([f"Zlarior → 50K {lit or '(not set)'}", f"ATLAS → 25K {atlas or '(not set)'}",
                      "both armed" if not arm_miss else "ATLAS armed, live switch off" if armed_b else
                      "live switch on, ATLAS not armed" if live else "not armed",
                      ("running" if not run_bad else "running, wrong set-up") if running else "stopped"]
                     + ([f"{', '.join(new)} NOT armed"] if new else []))
    why = None if running else resume_problem(cfg, b=b, live=live, new=new)
    try:
        blitz = blitz_status()                     # the BLITZ · 25K slot (account C, off by default)
    except Exception as e:
        blitz = {"on": False, "error": f"{e.__class__.__name__}: {e}"[:160]}
    return {"steps": steps, "all_green": all(done.values()), "say": say, "lit": lit or None, "atlas": atlas or None, "blitz": blitz,
            "suggest_lit": (_read(AUTOSTART).get("nt_account") or "").strip() or None, "running": running,
            "market_open": market_open(), "job": job_status(), "phrase": LIVE_PHRASE,
            "need_phrase": bool(not running and why), "resume_why": why, "keepalive": keepalive_view()}


def keepalive_view() -> dict:
    """The Start page / readiness: {"on": [labels], "off": [labels]} of the armed real accounts' 7-day keep-alive. Never raises."""
    try:
        from . import keepalive
        C = keepalive.load_config(None, path=_ka_path())
        rows = armed_accounts()
        return {"on": [l for k, l, n in rows if C["accounts"].get(k) is True],
                "off": [l for k, l, n in rows if C["accounts"].get(k) is not True],
                "consent_day": (C.get("consent") or {}).get("day")}
    except Exception:
        return {"on": [], "off": []}


# ---------------------------------------------------------------------------- one button: "Start trading"
# The Start page's big button runs every step in order in one job (`python -m engine.go --step auto`, step_auto below):
# update if behind, NinjaTrader open + connected, live bars, the Sim test (once), then the start. The start needs no typed
# phrase when the owner's auto-resume opt-in is valid for exactly the 50K (he typed I ACCEPT LIVE RISK for it; the kill
# switch clears it): then it is the same gate as the auto-resume after a reboot (engine/autoresume.decide), run in the
# server (resume_now). Otherwise the page asks for the phrase once and the job runs step_arm with it.
AUTO_WAIT_S = 20 * 60          # NinjaTrader log-in / live bars: the job waits this long, re-checking
NT_EVERY_S, FEED_EVERY_S = 10, 15
CLOCK_MAX_S = 5.0
CLOCK_TASK = "OlympusClock"          # the Scheduled Task FIX_CLOCK.bat registers (SYSTEM, every 15 min + boot): runs w32tm /resync
CLOCK_FIX_SAY = "double-click FIX_CLOCK.bat once, right-click > Run as administrator"   # the one plain sentence, everywhere
CLOCK_STEPS = CLOCK_FIX_SAY[0].upper() + CLOCK_FIX_SAY[1:] + " (it sets Windows' time service and a task, so it never needs you again)."


def resume_problem(cfg=None, optin=None, b=None, live=None, new=None) -> str | None:
    """Why "Start trading" needs the typed phrase (None = it does not): the auto-resume opt-in (data/auto_resume.json, made
    when the owner typed I ACCEPT LIVE RISK at a start) valid for exactly the saved 50K, the live switch on, ATLAS's 25K
    armed, and no added account (a Rapid, an engine.accounts row) still waiting for the phrase (new = unarmed_added())."""
    from . import autoresume
    cfg = _read(CFG) if cfg is None else cfg
    lit, atlas = _names(cfg)
    rec = autoresume.load(autoresume.OPTIN_PATH) if optin is None else optin
    if not lit or not atlas:
        return "the account names are not set"
    if not autoresume.valid(rec):
        return "auto-resume is off (the first start, or after the kill switch)"
    if str(rec.get("account") or "") != lit:
        return f"auto-resume is for {rec.get('account')}, not the 50K {lit}"
    if not (env_has_live() if live is None else live):
        return "the live switch is off"
    b = _b() if b is None else b
    if str(b.get("account") or "").strip() != atlas or b.get("armed") is not True:
        return "ATLAS's 25K is not armed"
    new = unarmed_added() if new is None else new
    if new:
        return f"{', '.join(new)} added but not armed yet"
    return None


def unarmed_added() -> list:
    """The accounts added with ADD_ACCOUNT / the account box / engine.accounts (a Rapid slot, an engine.accounts row) that are
    real, on and NOT armed yet: only step_arm (the typed phrase) arms them, so "Start trading" asks for the phrase instead
    of starting without them (2026-11-21: Start trading resumed the bot without the phrase and the new Rapid EOD 25K stayed
    'refused: start config is not armed'). Labels with the Name masked to its last 4 ("Rapid EOD 25K ..6020"). Never raises."""
    try:
        from . import account_cli
        out = []
        for r in account_cli.inventory():
            if r.get("role") not in ("rapid", "extra") or r.get("sim") or r.get("enabled", True) is False:
                continue
            if (r["role"] == "extra" and not r.get("cli")) or r.get("armed") is True:
                continue                   # an old multi_account row the phrase never arms / already armed
            lbl = account_cli.PLANS.get(r.get("plan"), {}).get("label") or "added account"
            out.append(f"{lbl}{' funded' if r.get('stage') == 'funded' else ''} ..{str(r['name'])[-4:]}")
        return out
    except Exception:
        return []


def start_body(cfg) -> dict:
    """The start config `engine.ninjatrader --start --account <50K>` sends (with the saved write_mode and the extra
    accounts), without any phrase."""
    body = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "present": True, "poll_sec": 60,
            "data_source": "ninjatrader", "nt_account": cfg.get("lit")}
    if cfg.get("write_mode"):
        body["nt_write_mode"] = cfg["write_mode"]
    try:
        from . import multi_account
        body = multi_account.merge_into_start(body, "")
    except Exception:
        pass
    return body


def resume_now(start_fn, connected=None, live_state=None, env=None, state_fn=None, optin=None, stop_fn=None) -> dict:
    """In the server: "Start trading" without the phrase. Refused unless resume_problem() is None AND the auto-resume gate
    passes (engine/autoresume.decide: NINJATRADER_LIVE=1 in this server, no kill switch / daily loss today, no failed start
    in the last 10 minutes, NinjaTrader CONNECTED). start_fn = Bot Control's start (the bot + its autostart record, the
    phrase stripped). After the start the routes are checked in the running bot and it is stopped when they are wrong
    (stop_fn = Bot Control's stop: the bot and its autostart record)."""
    from . import autoresume
    cfg = _read(CFG)
    why = resume_problem(cfg, optin=optin)
    if why:
        return {"ok": False, "error": f"Type I ACCEPT LIVE RISK to start: {why}.", "need": "phrase"}
    rec = autoresume.load(autoresume.OPTIN_PATH) if optin is None else optin
    body = start_body(cfg)
    if connected is None:
        connected = autoresume.nt_connected(body)
    if live_state is None:
        live_state = autoresume._read_json(os.path.join(ROOT, "data", "live_state.json"))
    d = autoresume.decide(rec, body, live_state, env=env, connected=connected)
    if not d["resume"]:
        return {"ok": False, "error": f"Not started: {d['reason']}.", "wait": d.get("wait")}
    try:
        r = start_fn(d["cfg"])
    except Exception as e:
        r = {"ok": False, "error": f"{e.__class__.__name__}: {e}"}
    if not r.get("ok") and "already running" not in str(r.get("error") or ""):
        return {"ok": False, "error": f"Not started: {r.get('error')}"}
    st = state_fn() if state_fn else _state()
    probs = verify_routes(cfg["lit"], cfg["atlas"], state=st)
    if probs:
        try:
            if stop_fn is not None:
                stop_fn()
        except Exception:
            pass
        return {"ok": False, "error": "Wrong account set-up, so the bot was stopped: " + "; ".join(probs), "stop": True}
    soft = soft_routes(cfg["lit"], cfg["atlas"], state=st)
    say = (f"Running Zlarior → 50K {cfg['lit']}; ATLAS NOT armed: {'; '.join(soft)}" if soft else
           f"Running: Zlarior → 50K {cfg['lit']} · ATLAS → 25K {cfg['atlas']}")
    return {"ok": True, "say": say, "soft": soft, "refused_accounts": d.get("refused_accounts") or []}


def sync_clock(run=None) -> dict:
    """The Start page's "Sync the clock": 1. `w32tm /resync` (Windows' own time service). 2. Refused (needs an administrator, or
    the time service is off): `schtasks /run /tn OlympusClock`, which works WITHOUT admin once FIX_CLOCK.bat registered the task
    (it runs as SYSTEM). 3. No such task: say plainly to double-click FIX_CLOCK.bat once (right-click > Run as administrator)."""
    if os.name != "nt" and run is None:
        return {"ok": False, "error": "Only on the Windows PC.", "steps": CLOCK_STEPS}
    run = run or subprocess.run

    def go_(cmd):
        try:
            r = run(cmd, capture_output=True, text=True, timeout=40)
            return (r.stdout or "") + (r.stderr or ""), r.returncode
        except Exception as e:
            return f"{e.__class__.__name__}: {e}", 1
    out, code = go_(["w32tm", "/resync"])
    low = out.lower()
    if code == 0 and "error" not in low and "denied" not in low and "not been started" not in low:
        return {"ok": True, "say": "Clock synced with internet time.", "out": out.strip()[-200:]}
    why = ("Windows asks for an administrator to sync the clock" if "denied" in low or "0x80070005" in low else
           "Windows' time service is off" if "not been started" in low or "0x80070426" in low else
           "Windows did not sync the clock")
    o2, c2 = go_(["schtasks", "/run", "/tn", CLOCK_TASK])
    l2 = o2.lower()
    if c2 == 0 and "error" not in l2 and "denied" not in l2 and "cannot find" not in l2 and "does not exist" not in l2:
        return {"ok": True, "say": f"Clock sync started by the {CLOCK_TASK} task (no administrator needed); it follows in a few seconds.",
                "via": "task", "out": o2.strip()[-200:]}
    gone = c2 != 0 or "cannot find" in l2 or "does not exist" in l2
    return {"ok": False, "error": f"{why}, and the {CLOCK_TASK} task is not set up yet: {CLOCK_FIX_SAY}." if gone else
            f"{why}: {CLOCK_FIX_SAY}.", "steps": CLOCK_STEPS, "out": (out.strip() + " | " + o2.strip())[-240:]}


def _note(stage, say, need=None, retry_s=None):
    """One plain line for the page: the job file's stage / say / need / retry_s, and the log."""
    print(f" {say}")
    try:
        j = _read(JOB_FILE)
        if j:
            j.update(stage=stage, say=say, need=need, retry_s=retry_s)
            _save(j, JOB_FILE)
    except Exception:
        pass


def step_auto(cfg, phrase="", py=sys.executable, after_update=False, sleep=time.sleep, wait_s=AUTO_WAIT_S) -> int:
    """"Start trading": every step in order, each skipped when done; NinjaTrader's log-in and the live bars are waited for
    (re-checked every 10 / 15 s); stops with one plain sentence (the page's retry_s = try again by itself, need = the
    owner must do something: names, phrase, market). 0 = running."""
    phrase = typed_phrase(phrase) if phrase else ""
    if bot_running():
        lit, atlas = _names(cfg)
        probs = verify_routes(lit, atlas) if lit and atlas else ["the account names are not set"]
        soft = soft_routes(lit, atlas) if not probs else []
        _note("running", ("Already running." + (f" ATLAS NOT armed: {'; '.join(soft)}." if soft else "")) if not probs else
              "Running with the wrong set-up: " + "; ".join(probs), need=None if not probs else "stop")
        return 0 if not probs else 1
    if not after_update:
        _note("update", "Looking for a newer version")
        if update(py):
            _note("update", "New version downloaded: restarting the bot server on it")
            if server_up():
                stop_server()
            start_server()
            env = {k: v for k, v in os.environ.items() if k != "LE_START_CONFIRM"}
            if phrase:
                env["LE_START_CONFIRM"] = phrase
            return subprocess.run([py, "-X", "utf8", "-m", "engine.go", "--step", "auto", "--after-update"], cwd=ROOT,
                                  env=env).returncode
    migrate()
    cfg = _read(CFG)
    lit, atlas = _names(cfg)
    if not lit or not atlas or lit == atlas:
        _note("accounts", "Set the two account names below (once): the 50K for Zlarior, the 25K for ATLAS.", need="names")
        return 1
    bad = mixup(lit, atlas)
    if bad:
        _note("accounts", f"Check the account names: {bad}.", need="names")
        return 1
    if setup_missing(cfg):
        _note("setup", "Setting up both accounts (allowlist, 50K balance and floor, ATLAS on the 25K)")
        cfg.pop("prepped", None)
        if step_prep(cfg):
            _note("setup", "The account setup failed (see the lines below). Trying again in a minute.", retry_s=60)
            return 1
    from . import autoresume
    if autoresume.nt_connected({"adapter": "ninjatrader"}) is not True:
        _note("nt", "Opening NinjaTrader")
        ensure_ninjatrader(wait_s=0, sleep=lambda s: None)
        t0 = time.time()
        while autoresume.nt_connected({"adapter": "ninjatrader"}) is not True:
            if time.time() - t0 > wait_s:
                _note("nt", "NinjaTrader is still not connected. Log in to NinjaTrader; the page tries again by itself. (In "
                            "NinjaTrader, Connections > Configure: tick 'Connect on startup' and it connects by itself.)",
                      retry_s=60)
                return 1
            _note("nt", "Log in to NinjaTrader and connect your MFFU account. This page goes on by itself.", retry_s=NT_EVERY_S)
            sleep(NT_EVERY_S)
    _note("feed", "NinjaTrader connected. Checking the live bars")
    t0 = time.time()
    while True:
        why = feed_problem()
        if why is None:
            break
        roll = _roll_text(why)              # the chart still on the old contract after the roll: its own fix
        if time.time() - t0 > wait_s:
            _note("feed", f"{why}. The page tries again by itself." if roll else
                  f"Still no live bars from NinjaTrader ({why}). In NinjaTrader: {FEED_FIX}. The page tries again by itself.",
                  retry_s=60)
            return 1
        _note("feed", f"{why}. Checking again every 15 s." if roll else
              f"No live bars from NinjaTrader ({why}). In NinjaTrader: {FEED_FIX}. Checking again every 15 s.",
              retry_s=FEED_EVERY_S)
        sleep(FEED_EVERY_S)
    if not all(sims_passed().values()):
        if not market_open():
            _note("sims", "The one-time Sim test needs the market open (Sunday 18:00 to Friday 17:00 ET). The page tries again "
                          "by itself.", need="market", retry_s=600)
            return 1
        _note("sims", "One-time Sim test on Sim101 (about 2 minutes; the dashboard restarts during it)")
        if step_sims(py, restart=True, cfg=cfg):
            _note("sims", "The Sim test failed. Nothing is armed. Trying again in 5 minutes.", retry_s=300)
            return 1
        cfg = _read(CFG)
    why = resume_problem(cfg)
    if why is None:
        _note("start", "Starting Zlarior and ATLAS (no phrase needed: auto-resume is on)")
        if server_up() and (server_stale() or env_newer_than_server()):
            stop_server()
        if not server_up() and not start_server():
            _note("start", "The bot server did not start. Trying again in a minute.", retry_s=60)
            return 1
        last = None
        for _ in range(3):                                  # a fresh server may resume the bot by itself first
            if bot_running():
                break
            try:
                r = _http("/api/next/start/resume", {}, timeout=120)
            except Exception as e:
                r = {"ok": False, "error": f"the bot server did not answer ({e.__class__.__name__})"}
            if r.get("ok") or bot_running():
                break
            if r.get("need") == "phrase":
                _note("arm", r.get("error") or "Type I ACCEPT LIVE RISK to start.", need="phrase")
                return 3
            last = str(r.get("error") or "Not started.")[:300]
            if r.get("stop"):
                break                                       # it started on the wrong account and was stopped: no retry here
            _note("start", last, retry_s=30)
            sleep(30)
        if not bot_running():
            _note("start", f"{last or 'Not started.'} Trying again in a minute.", retry_s=60)
            return 1
        probs = verify_routes(lit, atlas)
        if probs:
            if bot_running():
                from . import ninjatrader
                ninjatrader.main(["--stop"])
            _note("start", "Not running: " + "; ".join(probs) + ". Trying again in a minute.", retry_s=60)
            return 1
        soft = soft_routes(lit, atlas)        # ATLAS not armed: said once, no stop, no retry (the old 60 s Re-arm loop)
        _note("running", f"Running Zlarior → 50K {lit}; ATLAS NOT armed: {'; '.join(soft)}." if soft else
              f"Running: Zlarior → 50K {lit} · ATLAS → 25K {atlas}.")
        return 0
    if phrase != LIVE_PHRASE:
        _note("arm", f"Type I ACCEPT LIVE RISK once to arm every account ({why}).", need="phrase")
        return 3
    _note("arm", "Arming and starting: Zlarior → 50K, ATLAS → 25K" + "".join(f", {x}" for x in unarmed_added()))
    rc = step_arm(cfg, phrase, open_page=False)
    if rc:
        bad = [r for r in LAST_ROWS if not r["armed"]]
        _note("arm", "NOT TRADING: " + "; ".join(f"{r['label']}: {r['reason']} -> {r['fix']}" for r in bad[:2])[:400]
              if bad else "Arming did not finish (see the lines below). Press Start trading to try again.")
        return rc
    left = unarmed_added()                 # the phrase was typed but an added account could not be armed: said, never silent
    _note("running", f"Running: Zlarior → 50K {lit} · ATLAS → 25K {atlas}."
          + (f" NOT armed, so NOT trading: {', '.join(left)} (see the lines below)." if left else ""))
    return 0


# ---------------------------------------------------------------------------- the Accounts panel
def nt_names(folder=None) -> list:
    """NinjaTrader account Names the page offers as a pick list (no Sim): LE_BarFeed's accounts.csv rows and the position
    files in NinjaTrader's outgoing folder."""
    from .ninjatrader import is_sim, default_folder
    out = {}
    try:
        from . import broker_balance
        for n, r in (broker_balance.read(folder=folder).get("rows") or {}).items():
            if n and not is_sim(n):
                out[n] = {"name": n, "balance": (r.get("netliq") or r.get("cash")) if r.get("fresh") else None,
                          "src": "NinjaTrader balance"}
    except Exception:
        pass
    try:
        og = os.path.join(folder or default_folder(), "outgoing")
        for f in os.listdir(og):
            if f.lower().endswith("_position.txt") and "_" in f[:-13]:
                n = f[:-13].split("_", 1)[1].strip()
                if n and not is_sim(n) and n not in out:
                    out[n] = {"name": n, "balance": None, "src": "NinjaTrader positions"}
    except Exception:
        pass
    return sorted(out.values(), key=lambda r: r["name"])


def _money(name, preset, main=False, balances=None) -> dict:
    from . import eval_life, multi_account as ma
    R = ma.rules_of({"preset": preset})
    try:
        anc = eval_life.load_anchor(name, path=ANCHOR_PATH or eval_life.anchor_path(), main=main)
    except Exception:
        anc = None
    bal = (nt_balances() if balances is None else balances).get(name)
    return {"balance": float(bal) if bal is not None else (anc or {}).get("balance", R["start"]),
            "floor": (anc or {}).get("floor", R["start"] - R["mll"]), "as_of": (anc or {}).get("as_of"),
            "source": "NinjaTrader" if bal is not None else "MFFU numbers you entered" if anc else "plan start"}


def accounts(cards=None) -> dict:
    """Every account the bot knows: Zlarior's 50K (data/start_bot.json), ATLAS's 25K (second_model.json account_b), the
    extra / funded accounts (data/accounts.json). cards = the running bot's two account cards (engine/pc_cc_api) laid over."""
    from . import multi_account as ma
    cfg = _read(CFG)
    lit, atlas = _names(cfg)
    b, bals, rows = _b(), nt_balances(), []
    b_on = str(b.get("account") or "").strip()
    cards = cards or {}
    if lit:
        rows.append({"name": lit, "bot": "Zlarior", "role": "main", "plan": "builder50k", "plan_label": "MFFU Builder 50K",
                     "state": "eval", "armed": None, **_money(lit, "mffu_builder_50k", True, bals)})
    if b_on or atlas:
        n = b_on or atlas
        plan = str(b.get("plan") or "builder25k") if b_on else "builder25k"
        funded = bool(b_on) and str(b.get("stage") or "").lower() == "funded"       # engine/account_b.to_funded (owner-run)
        rows.append({"name": n, "bot": "ATLAS", "role": "b", "plan": plan,
                     "plan_label": PLANS.get(plan, ("", plan))[1] + (" funded" if funded else ""),
                     "state": "funded" if funded else "eval", "armed": b.get("armed") is True if b_on else False,
                     "start": b.get("funded_start") if funded else b.get("eval_start"),
                     "note": (f"passed eval {b.get('eval_account')}" if funded and b.get("eval_account") else None) if b_on == atlas
                     else "not set up yet (Run setup)" if not b_on else f"the saved 25K is {atlas or 'none'}",
                     **_money(n, PLANS.get(plan, ("mffu_builder_25k",))[0], False, bals)})
    for e in _extras():
        n = ma.normalize(e)
        plan = next((k for k, v in PLANS.items() if v[0] == n["preset"]), n["preset"])
        rows.append({"name": n["nt_account"] or n["name"], "id": n["id"], "bot": "Zlarior", "role": "extra", "plan": plan,
                     "plan_label": f"{n['firm']} {n['plan']}".strip(), "state": "funded" if n["mode"] == "funded" else "eval",
                     "armed": n["armed"], "enabled": n["enabled"], "start": (n["funded"] or {}).get("start") or n["eval_start"],
                     "note": None if not n["problem"] or n["problem"] == "disabled in the config" else n["problem"],
                     **_money(n["nt_account"], n["preset"], False, bals)})
    try:                                            # the Rapid EOD slots (engine/rapid.py): LIT + ATLAS on one account
        from . import rapid
        for sl, blk in rapid.read_all():
            n = str(blk.get("account") or "").strip()
            funded = str(blk.get("stage") or "").lower() == "funded"
            info = rapid.plan_info(blk)
            rows.append({"name": n, "id": sl, "bot": "Zlarior + ATLAS", "role": "rapid", "plan": "rapideod25" if "25" in
                         str(info.get("label") or "") else "rapideod", "plan_label": f"MFFU {info.get('label') or 'Rapid EOD'}"
                         + (" funded" if funded else ""), "state": "funded" if funded else "eval",
                         "armed": blk.get("armed") is True, "start": blk.get("funded_start") if funded else blk.get("start"),
                         "note": None, **_money(n, str(blk.get("plan") or "mffu_rapid_eod_50k"), False, bals)})
    except Exception:
        pass
    cb = _c()                                       # BLITZ's own 25K (account C, engine/account_c.py): only when set
    if str(cb.get("account") or "").strip():
        from .ninjatrader import is_sim
        n = str(cb["account"]).strip()
        funded = str(cb.get("stage") or "").lower() == "funded"
        rows.append({"name": n, "bot": "BLITZ", "role": "c", "plan": "builder25k",
                     "plan_label": "MFFU Builder 25K" + (" funded" if funded else "") + (" (Sim test)" if is_sim(n) else ""),
                     "state": "funded" if funded else "eval", "armed": cb.get("armed") is True if not is_sim(n) else None,
                     "start": cb.get("funded_start") if funded else cb.get("eval_start"),
                     "note": (f"passed eval {cb.get('eval_account')}" if funded and cb.get("eval_account") else
                              "Sim test: the real route on a Sim account, no real money" if is_sim(n) else None),
                     **_money(n, "mffu_builder_25k", False, bals)})
    for r in rows:
        c = cards.get("lit" if r["role"] == "main" else "atlas" if r["role"] == "b" else "") or {}
        if c and not c.get("error") and c.get("balance") is not None and c.get("configured") is not False:
            r.update(balance=c.get("balance"), floor=c.get("floor", r["floor"]), source="the running bot")
            if c.get("status"):
                r["eval_status"] = str(c["status"]).lower()
    return {"rows": rows, "picks": nt_names(), "plans": {k: v[1] for k, v in PLANS.items()}, "today": session_day()}


def add_account(name, plan="builder50k", strategy="zlarior", start=None) -> dict:
    """Add one account: the first 50K is Zlarior's main account, a 25K for ATLAS is account B, any other is an extra
    Zlarior account (data/accounts.json, disarmed). Allowlisted; never armed here."""
    name, plan, strategy = str(name or "").strip(), str(plan or "").lower(), str(strategy or "").lower()
    if plan not in PLANS:
        return {"ok": False, "error": "Pick a plan: Builder 50K or Builder 25K."}
    if strategy == "blitz":
        if plan != "builder25k":
            return {"ok": False, "error": "BLITZ trades a 25K (MFFU allows one funded 50K per person: Zlarior's): pick Builder 25K."}
        if str(_c().get("account") or "").strip():
            return {"ok": False, "error": f"BLITZ already has the 25K {_c().get('account')}: remove it first."}
        return set_blitz(name, start)
    if strategy not in ("zlarior", "atlas"):
        return {"ok": False, "error": "Pick the bot: Zlarior, ATLAS or BLITZ."}
    try:
        start = dt.date.fromisoformat(str(start)).isoformat() if start else session_day()
    except ValueError:
        return {"ok": False, "error": "Start day as yyyy-mm-dd."}
    preset, label, size = PLANS[plan]
    bad = slot_problem(name, size)
    if bad:
        return {"ok": False, "error": f"Not added: {bad}."}
    cfg = _read(CFG)
    lit, atlas = _names(cfg)
    b = _b()
    who = role_of(name, cfg, b)
    if who:
        return {"ok": False, "error": f"Not added: {name} is already {who}. One account trades for one bot only."}
    if bot_running():
        return {"ok": False, "error": "Stop the bot first: it reads the accounts when it starts."}
    if strategy == "atlas":
        if plan != "builder25k":
            return {"ok": False, "error": "ATLAS trades the 25K (Zlarior the 50K): pick Builder 25K."}
        b_on = str(b.get("account") or "").strip()
        if b_on or atlas:
            return {"ok": False, "error": f"ATLAS already has the 25K {b_on or atlas}: remove it first."}
        from . import account_b
        r = account_b.set_account_b(name, plan="builder25k", start=start, path=SECOND_PATH)
        if not r.get("ok"):
            return {"ok": False, "error": f"Not added: {r.get('error')}"}
        _allow(name)
        cfg["atlas"] = name
        _save(cfg)
        return {"ok": True, "say": f"ATLAS → 25K {name}, first session {start}. Not armed."}
    if not lit and plan == "builder50k":
        _allow(name)
        cfg["lit"] = name
        cfg.pop("prepped", None)
        _save(cfg)
        return {"ok": True, "say": f"Zlarior → 50K {name}. Not armed. Set its MFFU balance and floor with Change balance."}
    if not lit:
        return {"ok": False, "error": "Zlarior's main account is the 50K: add the 50K first."}
    # an extra Zlarior account: the same code as `engine.accounts add` (audit Package A: this branch wrote an untagged row
    # that START never armed or reported, and skipped the name / MFFU-limit checks)
    from . import account_cli
    r = account_cli.add(plan, name, start=start)
    if not r.get("ok"):
        return {"ok": False, "error": "Not added: " + str(r.get("error") or "see the log")}
    return {"ok": True, "say": f"Zlarior also trades {name} ({label}, from {start}). Not armed: armed at the next START "
                               "(you type the phrase).", "lines": [r.get("say") or ""] + list(r.get("notes") or [])}


def remove_account(name) -> dict:
    """Take one account off its bot (the bot stopped). The name leaves the allowlist when no bot uses it any more."""
    name = str(name or "").strip()
    cfg = _read(CFG)
    lit, atlas = _names(cfg)
    b_on = str(_b().get("account") or "").strip()
    ex = next((e for e in _extras() if name and name in (str(e.get("nt_account") or "").strip(), str(e.get("id") or ""))), None)
    c_on = str(_c().get("account") or "").strip()
    if name and not ex and name not in (lit, atlas, b_on, c_on) and str(role_of(name) or "").startswith("the Rapid EOD"):
        if bot_running():
            return {"ok": False, "error": "Stop the bot first: it reads the accounts when it starts."}
        from . import account_cli                   # the same code as `engine.accounts remove` (the Rapid's own off switch)
        r = account_cli.remove(name)
        return {"ok": bool(r.get("ok")), "say": r.get("say"), "error": r.get("error")}
    if name and name == c_on and name not in (lit, atlas, b_on) and not ex:
        if bot_running():
            return {"ok": False, "error": "Stop the bot first: it reads the accounts when it starts."}
        r = set_blitz("off")
        if not r.get("ok"):
            return {"ok": False, "error": f"Not removed: {r.get('error')}"}
        if not role_of(name):
            try:
                _allow(name, remove=True)
            except ValueError:
                pass
        return {"ok": True, "say": f"Removed {name} (BLITZ's 25K): BLITZ is back to paper only."}
    if not name or not (name in (lit, atlas, b_on) or ex):
        return {"ok": False, "error": f"No account {name!r} here."}
    if bot_running():
        return {"ok": False, "error": "Stop the bot first: it reads the accounts when it starts."}
    if name == lit:
        cfg.pop("lit", None)
        cfg.pop("prepped", None)
        _save(cfg)
        what = "Zlarior's 50K"
    elif name in (atlas, b_on):
        if b_on == name:
            from . import account_b
            r = account_b.set_account_b(None, path=SECOND_PATH)
            if not r.get("ok"):
                return {"ok": False, "error": f"Not removed: {r.get('error')}"}
        if atlas == name:
            cfg.pop("atlas", None)
            cfg.pop("prepped", None)
            _save(cfg)
        what = "ATLAS's 25K"
    else:
        from . import multi_account as ma
        rc, lines = _quiet(ma.main, ["--remove", "--id", str(ex.get("id")), "--file", _accounts_path()])
        if rc:
            return {"ok": False, "error": "Not removed: " + (lines[-1] if lines else "see the log")}
        what = f"the account {ex.get('id')}"
        name = str(ex.get("nt_account") or name)
    if not role_of(name):
        try:
            _allow(name, remove=True)
        except ValueError:
            pass
    return {"ok": True, "say": f"Removed {name} ({what})."}


def set_anchor(name, balance, floor, as_of) -> dict:
    """Change an eval account's MFFU balance / floor as of a day (engine/eval_life.set_anchor; Zlarior's 50K = the main)."""
    from . import eval_life
    try:
        balance, floor = float(balance), float(floor)
        as_of = dt.date.fromisoformat(str(as_of)).isoformat()
    except (TypeError, ValueError):
        return {"ok": False, "error": "Balance and floor as numbers, as of yyyy-mm-dd."}
    lit, _ = _names()
    name = str(name or "").strip()
    rc, lines = _quiet(eval_life.set_anchor, balance, floor, as_of, None if (not name or name == lit) else name,
                       ANCHOR_PATH or eval_life.anchor_path())
    lines = [ln for ln in lines if not ln.startswith("File:")]
    if rc:
        return {"ok": False, "error": lines[-1] if lines else "not saved", "lines": lines}
    return {"ok": True, "say": f"{name or lit}: balance ${balance:,.2f}, floor ${floor:,.2f} as of {as_of}.", "lines": lines}


def to_funded(name, funded_name, start, plan=None, balance=None) -> dict:
    """After a pass: the funded account (its new NinjaTrader Name) joins as a funded account. Zlarior's eval: engine/
    eval_life.to_funded (data/accounts.json mode funded, disarmed). ATLAS's 25K (account B): engine/account_b.to_funded
    (the local block's funded stage on the new Name, disarmed) and the saved ATLAS Name follows it."""
    from . import eval_life
    row = next((r for r in accounts()["rows"] if r["name"] == str(name or "").strip()), None)
    if row is None or row.get("state") != "eval":
        return {"ok": False, "error": f"No eval account {name!r} here: pick the account that passed."}
    if row.get("role") == "b":
        return _b_to_funded(row, funded_name, start, balance)
    if row.get("role") == "c":
        return _c_to_funded(row, funded_name, start, balance)
    if row.get("role") == "rapid":                  # the Rapid's own funded switch (engine.accounts add --funded / one tap)
        return {"ok": False, "error": "A Rapid EOD goes funded with the one tap on the Start page (Move Zlarior + ATLAS here) "
                                      "or: python -X utf8 -m engine.accounts add --plan rapideod25 --name \"<funded Name>\" --funded"}
    plan = str(plan or row.get("plan") or "builder50k").lower()
    if plan not in PLANS:
        return {"ok": False, "error": "Pick a plan: Builder 50K or Builder 25K."}
    funded_name = str(funded_name or "").strip()
    try:
        start = dt.date.fromisoformat(str(start)).isoformat()
    except (TypeError, ValueError):
        return {"ok": False, "error": "First funded day as yyyy-mm-dd."}
    bad = slot_problem(funded_name, PLANS[plan][2])
    if bad:
        return {"ok": False, "error": f"Not switched: {bad}."}
    who = role_of(funded_name)
    if who and not who.startswith("the funded account"):
        return {"ok": False, "error": f"Not switched: {funded_name} is already {who}. The funded account has its own Name."}
    if bot_running():
        return {"ok": False, "error": "Stop the bot first: it reads the accounts when it starts."}
    rc, lines = _quiet(eval_life.to_funded, funded_name, start, plan=plan, path=_accounts_path())
    if rc:
        return {"ok": False, "error": "Not switched: " + (lines[-1] if lines else "see the log"), "lines": lines}
    _allow(funded_name)
    try:                                   # tagged like `engine.accounts add` rows, so START's arm step arms + reports it
        from . import account_cli, multi_account as ma
        rows = ma.load_file(_accounts_path())
        hit = False
        for r in rows:
            if str(r.get("nt_account") or "").strip() == funded_name and not isinstance(r.get("cli"), dict):
                r["cli"] = {"by": account_cli.TAG, "plan": plan, "bots": "lit", "added": session_day()}
                hit = True
        if hit:
            ma.save_file(rows, _accounts_path())
    except Exception as e:
        lines.append(f"[..] could not tag {funded_name} for START ({e.__class__.__name__}): arm it with START BOT")
    return {"ok": True, "say": f"{funded_name} is funded ({PLANS[plan][1]}) from {start}. Not armed: armed at the next START "
                               "(you type the phrase).", "lines": [ln for ln in lines if "python" not in ln]}


def _b_to_funded(row, funded_name, start, balance=None) -> dict:
    """ATLAS's passed 25K -> its funded account (engine/account_b.to_funded): the funded stage in data/account_b.json on
    the new Name, disarmed, allowlisted; data/start_bot.json "atlas" = the new Name (setup stays done: no launch prep
    again, it would not reset the funded stage anyway)."""
    from . import account_b
    funded_name = str(funded_name or "").strip()
    try:
        start = dt.date.fromisoformat(str(start)).isoformat()
    except (TypeError, ValueError):
        return {"ok": False, "error": "First funded day as yyyy-mm-dd."}
    bad = slot_problem(funded_name, "25K" if row.get("plan") == "builder25k" else "50K")
    if bad:
        return {"ok": False, "error": f"Not switched: {bad}."}
    cfg = _read(CFG)
    who = role_of(funded_name, cfg)
    if who:
        return {"ok": False, "error": f"Not switched: {funded_name} is already {who}. The funded account has its own Name."}
    if bot_running():
        return {"ok": False, "error": "Stop the bot first: it reads the accounts when it starts."}
    lit, _ = _names(cfg)
    r = account_b.to_funded(funded_name, start, balance, path=SECOND_PATH, allow_path=ALLOW_PATH, lit_account=lit)
    if not r.get("ok"):
        return {"ok": False, "error": f"Not switched: {r.get('error')}"}
    cfg["atlas"] = funded_name
    _save(cfg)
    return {"ok": True, "say": f"ATLAS → funded {funded_name} from {start} (passed eval {row['name']}). Funded sizing: {r['rule']}. "
                               "Not armed: arm it at the next start (you type the phrase).",
            "lines": [r["say"]] + ([f"The eval's history is kept in {os.path.basename(r['archived'])}"] if r.get("archived") else [])}


# ---------------------------------------------------------------------------- BLITZ's own 25K (account C, engine/account_c.py)
# The Start page's third slot "BLITZ · 25K" next to "Zlarior · 50K" and "ATLAS · 25K". OFF by default (data/account_c.json
# absent / null = the bot is exactly as before). Sim test = BLITZ on a NinjaTrader Sim account (the real route, no real money);
# a real MFFU 25K trades only after the owner arms it here with the typed phrase (and the bot runs live: phrase + live
# switch, engine/ninjatrader._live_gate). Nothing here arms by itself.
def _c_root() -> str:
    """The folder whose data/account_c.json is account C's block: next to SECOND_PATH (tests: their temp copy), else ROOT."""
    return os.path.dirname(os.path.abspath(SECOND_PATH)) if SECOND_PATH else ROOT


def _c() -> dict:
    from . import account_c
    return account_c.raw_cfg(_c_root()) or {}


def blitz_status(c=None) -> dict:
    """The BLITZ slot: on / off, the account, Sim or real, armed, the eval start, a problem, the stage."""
    from . import account_c
    from .ninjatrader import is_sim
    c = _c() if c is None else c
    name = str(c.get("account") or "").strip()
    if not name:
        return {"on": False, "say": "BLITZ · 25K is off (the scalper trades only on paper: its shadow ledgers)", "phrase": LIVE_PHRASE}
    lit, atlas = _names()
    sp = account_c.normalize(c, lit_account=lit or None, b_account=str(_b().get("account") or atlas or "").strip() or None)
    sim = is_sim(name)
    say = (f"BLITZ → {'Sim test on ' if sim else '25K '}{name}" + (" · funded" if c.get("stage") == "funded" else "")
           + (" · armed" if c.get("armed") is True else "" if sim else " · not armed (Sim only until you arm it)"))
    return {"on": True, "name": name, "sim": sim, "armed": c.get("armed") is True, "start": c.get("eval_start"), "stage": c.get("stage") or "eval",
            "problem": sp.get("problem") if sp else None, "params": bool(c.get("params")), "say": say, "phrase": LIVE_PHRASE}


def set_blitz(name, start=None) -> dict:
    """The BLITZ slot's "Set": BLITZ's own account = name (a Sim account = the Sim test; an MFFU 25K = its real account,
    NOT armed), or "off". A running bot picks the change up at its next poll, once BLITZ is flat (LiveBot._sync_account_c).
    Refused on Zlarior's or ATLAS's account, or when engine.ninjatrader --selftest fails (account_c.set_account_c)."""
    from . import account_c
    from .ninjatrader import is_sim
    name = str(name or "").strip()
    if not name or name.lower() == "off":
        r = account_c.set_account_c(None, root=_c_root())
        return {**r, "say": "BLITZ · 25K is off: the bot is exactly as before (the BLITZ paper shadow keeps running)."} if r.get("ok") else r
    try:
        start = dt.date.fromisoformat(str(start)).isoformat() if start else session_day()
    except ValueError:
        return {"ok": False, "error": "Start day as yyyy-mm-dd."}
    if not is_sim(name):
        bad = slot_problem(name, "25K")
        if bad:
            return {"ok": False, "error": f"Not set: {bad}."}
    cfg = _read(CFG)
    who = role_of(name, cfg)
    if who and who != "BLITZ's 25K":
        return {"ok": False, "error": f"Not set: {name} is already {who}. BLITZ needs its own account."}
    lit, atlas = _names(cfg)
    r = account_c.set_account_c(name, plan="builder25k", start=start, root=_c_root(), lit_account=lit or None,
                                b_account=str(_b().get("account") or atlas or "").strip() or None)
    if not r.get("ok"):
        return {"ok": False, "error": f"Not set: {r.get('error')}"}
    if not is_sim(name):
        _allow(name)
    return {"ok": True, "sim": is_sim(name),
            "say": (f"BLITZ Sim test → {name} from {start}: the real route on a Sim account, no real money." if is_sim(name) else
                    f"BLITZ → 25K {name}, first session {start}. NOT armed: Sim only until you arm it (you type the phrase).")}


def arm_c(phrase) -> dict:
    """The BLITZ slot's "Arm BLITZ": only with the owner's typed I ACCEPT LIVE RISK, on the saved MFFU 25K (a Sim account
    needs no arming). Writes account_c "armed": true; the running bot picks it up once BLITZ is flat (a real account also
    needs the bot started with the phrase and the live switch: engine/ninjatrader._live_gate)."""
    from . import account_c
    from .ninjatrader import is_sim
    if typed_phrase(str(phrase or "")) != LIVE_PHRASE:
        return {"ok": False, "error": "Type I ACCEPT LIVE RISK exactly. Nothing is armed."}
    c = _c()
    name = str(c.get("account") or "").strip()
    if not name:
        return {"ok": False, "error": "BLITZ has no account yet: set its 25K first."}
    if is_sim(name):
        return {"ok": False, "error": f"{name} is a Sim account: the Sim test needs no arming."}
    r = account_c.arm(name, root=_c_root())
    if not r.get("ok"):
        return {"ok": False, "error": f"Not armed: {r.get('error')}"}
    return {"ok": True, "say": f"BLITZ armed on the 25K {name}. It trades real money once the bot runs live (the start with the phrase)."}


def _c_to_funded(row, funded_name, start, balance=None) -> dict:
    """BLITZ's passed 25K -> its funded account (engine/account_c.to_funded): the funded stage on the new Name, disarmed."""
    from . import account_c
    funded_name = str(funded_name or "").strip()
    try:
        start = dt.date.fromisoformat(str(start)).isoformat()
    except (TypeError, ValueError):
        return {"ok": False, "error": "First funded day as yyyy-mm-dd."}
    bad = slot_problem(funded_name, "25K")
    if bad:
        return {"ok": False, "error": f"Not switched: {bad}."}
    who = role_of(funded_name)
    if who:
        return {"ok": False, "error": f"Not switched: {funded_name} is already {who}. The funded account has its own Name."}
    if bot_running():
        return {"ok": False, "error": "Stop the bot first: it reads the accounts when it starts."}
    lit, atlas = _names()
    r = account_c.to_funded(funded_name, start, balance, root=_c_root(), allow_path=ALLOW_PATH, lit_account=lit or None,
                            b_account=str(_b().get("account") or atlas or "").strip() or None)
    if not r.get("ok"):
        return {"ok": False, "error": f"Not switched: {r.get('error')}"}
    return {"ok": True, "say": f"BLITZ → funded {funded_name} from {start} (passed eval {row['name']}). Funded sizing: {r['rule']}. "
                               "Not armed: arm it on the BLITZ slot (you type the phrase)."}


# ---------------------------------------------------------------------------- step jobs (Sim test, arm + start)
def _pid_alive(pid) -> bool:
    try:
        import psutil
        return psutil.pid_exists(int(pid))
    except ImportError:
        pass
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"], capture_output=True, text=True)
        return str(int(pid)) in (r.stdout or "")
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def job_status() -> dict:
    """The dashboard's step job: running or done, its exit code and its last lines."""
    j = _read(JOB_FILE)
    if not j:
        return {"step": None, "running": False, "state": None, "lines": []}
    max_s = AUTO_MAX_S if j.get("step") == "auto" else JOB_MAX_S
    running = j.get("state") in ("starting", "running") and time.time() - float(j.get("t0") or 0) < max_s \
        and (not j.get("pid") or _pid_alive(j["pid"]))
    try:
        with open(JOB_LOG, encoding="utf-8", errors="replace") as fh:
            lines = [ln.rstrip() for ln in fh.read().splitlines() if ln.strip()][-60:]
    except OSError:
        lines = []
    return {"step": j.get("step"), "running": running, "state": "running" if running else "done" if j.get("state") == "done"
            else "stopped", "rc": j.get("rc"), "t0": j.get("t0"), "t1": j.get("t1"),
            "stage": j.get("stage"), "say": j.get("say"), "need": j.get("need"), "retry_s": j.get("retry_s"),
            "lines": [ln for ln in lines if LIVE_PHRASE not in ln]}


def job_start(step, phrase=None, py=sys.executable, popen=None) -> dict:
    """Start one step in its own window (`python -m engine.go --step sims|arm|auto`): it may stop and start the server
    the page runs on, so it cannot run inside it. The phrase reaches it in its environment, never on its command line.
    "auto" = the one "Start trading" button (step_auto); its phrase is optional (needed only when resume_problem says so)."""
    if step not in ("sims", "arm", "auto"):
        return {"ok": False, "error": "unknown step"}
    if job_status()["running"]:
        return {"ok": False, "error": "A step is already running: wait for it to finish."}
    if step == "auto":
        phrase = typed_phrase(phrase) if phrase else None
        if phrase and phrase != LIVE_PHRASE:
            return {"ok": False, "error": "Type I ACCEPT LIVE RISK exactly (or leave it empty). Nothing is armed."}
    if step == "arm" and phrase != LIVE_PHRASE:
        return {"ok": False, "error": "Type I ACCEPT LIVE RISK exactly. Nothing is armed."}
    if bot_running():
        return {"ok": False, "error": "Already running." if step == "auto" else "Stop the bot first (Bot control or STOP BOT)."}
    if step == "auto":
        pass
    elif step == "arm":
        bad = arm_problem(_read(CFG))
        if bad:
            return {"ok": False, "error": f"Not yet: {bad}."}
    elif not market_open():
        return {"ok": False, "error": "The market is closed (open Sun 18:00 ET - Fri 17:00 ET, not 17:00-18:00)."}
    elif (fp := feed_problem()) is not None:
        return {"ok": False, "error": f"{fp}." if _roll_text(fp) else f"No live bars from NinjaTrader: {FEED_FIX}."}
    os.makedirs(os.path.dirname(JOB_LOG), exist_ok=True)
    with open(JOB_LOG, "w", encoding="utf-8") as fh:
        fh.write(f" {dt.datetime.now().strftime('%H:%M:%S')} starting: {step}\n")
    _save({"step": step, "state": "starting", "t0": time.time()}, JOB_FILE)
    env = {k: v for k, v in os.environ.items() if k != "LE_START_CONFIRM"}
    if phrase:
        env["LE_START_CONFIRM"] = phrase
    cmd = [py, "-X", "utf8", "-m", "engine.go", "--step", step]
    popen = popen or POPEN or subprocess.Popen
    if os.name == "nt":
        popen(["cmd", "/c", "start", f"LE Start - {step}", "/min", *cmd], cwd=ROOT, env=env)
    else:
        popen(cmd, cwd=ROOT, env=env, start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL)
    return {"ok": True, "step": step}


class _Tee:
    def __init__(self, *outs):
        self.outs = outs

    def write(self, s):
        for o in self.outs:
            try:
                o.write(s)
                o.flush()
            except Exception:
                pass
        return len(s)

    def flush(self):
        pass


def job_main(step, after_update=False) -> int:
    """`python -m engine.go --step sims|arm|auto`: one step for the dashboard, its lines in logs/start_job.log."""
    os.makedirs(os.path.dirname(JOB_LOG), exist_ok=True)
    log = open(JOB_LOG, "a", encoding="utf-8")
    old = sys.stdout
    sys.stdout = _Tee(old, log)
    j = _read(JOB_FILE)
    j.update(step=step, state="running", pid=os.getpid(), t0=j.get("t0") or time.time())
    _save(j, JOB_FILE)
    rc = 1
    try:
        cfg = _read(CFG)
        if step == "sims":
            if bot_running():
                print(" [FIX] The bot is running: stop it first.")
            else:
                rc = step_sims(restart=True, cfg=cfg)
        elif step == "arm":
            phrase = os.environ.pop("LE_START_CONFIRM", "")
            print(f" Zlarior -> 50K {cfg.get('lit')}    ATLAS -> 25K {cfg.get('atlas')}")
            rc = step_arm(cfg, phrase, open_page=False)
        elif step == "auto":
            rc = step_auto(cfg, os.environ.pop("LE_START_CONFIRM", ""), after_update=after_update)
    except Exception as e:
        print(f" [FIX] {e.__class__.__name__}: {e}. Send Claude a photo of this page.")
    finally:
        j = _read(JOB_FILE)
        j.update(state="done", rc=rc, t1=time.time())
        _save(j, JOB_FILE)
        sys.stdout = old
        log.close()
    return rc


def _open():
    try:
        import webbrowser
        webbrowser.open(f"http://localhost:{PORT}")
    except Exception:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-pull", action="store_true", help="skip the git pull of main")
    ap.add_argument("--step", choices=["sims", "arm", "auto"], help="one step for the dashboard Start page (logs/start_job.log)")
    ap.add_argument("--after-update", action="store_true", help="--step auto, after it updated itself (no second update)")
    a = ap.parse_args(argv)
    if a.step:
        return job_main(a.step, after_update=a.after_update)
    try:
        return run(dry=a.dry_run, pull=not a.no_pull)
    except (KeyboardInterrupt, EOFError):
        # night-mondaysim 2026-11-23: Ctrl+C or a closed window input = one plain line, never a traceback (nothing was armed
        # unless the phrase had already been typed; a step already done is skipped next time)
        print("\n [FIX] START BOT stopped before the end. Double-click START_BOT.bat (or MONDAY_SETUP.bat) again: done steps are skipped.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
