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
    os.replace(tmp, path)


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
    """CME Globex: Sun 18:00 ET -> Fri 17:00 ET, closed 17:00-18:00 ET every weekday."""
    from zoneinfo import ZoneInfo
    t = now or dt.datetime.now(ZoneInfo("America/New_York"))
    wd, h = t.weekday(), t.hour
    if wd == 5 or (wd == 6 and h < 18) or (wd == 4 and h >= 17):
        return False
    return h != 17


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


def verify_routes(lit, atlas, state=None, b=None) -> list:
    """After the start: the problems with who trades where ([] = Zlarior on the 50K, ATLAS armed on the 25K)."""
    from . import second
    if state is None:
        try:
            state = _http("/api/live/state")
        except Exception as e:
            return [f"bot state not readable ({e.__class__.__name__})"]
    b = second.load_cfg(SECOND_PATH).get("account_b") if b is None else b
    cfg = (state or {}).get("cfg") or {}
    out = []
    if not (state or {}).get("running"):
        out.append("the bot is not running")
    if cfg.get("nt_account") != lit:
        out.append(f"Zlarior is on {cfg.get('nt_account')!r}, not the 50K {lit!r}")
    for e in cfg.get("accounts") or []:                 # extra LIT accounts (data/accounts.json) must not include the 25K
        if isinstance(e, dict) and e.get("enabled", True) is not False and str(e.get("nt_account") or "") == atlas:
            out.append(f"Zlarior also lists the 25K {atlas!r} as an extra account (data/accounts.json)")
    if cfg.get("adapter") != "ninjatrader":
        out.append(f"the bot runs on {cfg.get('adapter')!r}, not NinjaTrader")
    if str((b or {}).get("account") or "") != atlas:
        out.append(f"ATLAS is on {(b or {}).get('account')!r}, not the 25K {atlas!r}")
    elif (b or {}).get("armed") is not True:
        out.append("ATLAS's 25K is not armed")
    if str((b or {}).get("plan") or "") != "builder25k":
        out.append(f"ATLAS plan is {(b or {}).get('plan')!r}, not builder25k")
    return out


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
    subprocess.Popen(["cmd", "/c", "start", "Liquidity Engine bot", *_ps(RUN_BOT)], cwd=ROOT)
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
    """None = LE_BarFeed's MNQ 5m file is fresh; else why not (engine/ninjatrader.NinjaTraderBars.recent_bars)."""
    try:
        from .ninjatrader import NinjaTraderBars, default_folder
        df, why, _ = NinjaTraderBars(default_folder()).recent_bars("NQ", "5m", "1d")
        return None if df is not None else (why or "no bars")
    except Exception as e:
        return f"{e.__class__.__name__}: {e}"


def ensure_feed(wait_s=900, problem=None, sleep=time.sleep) -> bool:
    """The NinjaTrader bar feed fresh (the Sim test and every trade need it); shows the chart fix once and waits up to
    15 min for it. True = fresh."""
    problem = problem or feed_problem
    why = problem()
    if why is None:
        return True
    print(f"     The bot gets no live bars from NinjaTrader ({why}).")
    print("     Fix it in NinjaTrader now (this window waits and goes on by itself):")
    print("       1. Open the MNQ 12-26 chart, set it to 5 Minute (or New > Chart: MNQ 12-26, Minute, 5).")
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
    from . import autoupdate, generated_files
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


def step_arm(cfg, phrase, dry=False, open_page=True) -> int:
    """4. only with the typed phrase: NINJATRADER_LIVE in .env.local.ps1, the server (re)started so it reads it, the 25K
    armed, the bot started on the 50K, the routes checked in the running bot (stopped when wrong), auto-resume on, the
    Startup-folder shortcuts, then the launch checklist."""
    if phrase != LIVE_PHRASE:
        print(" Stopped. Nothing is armed.")
        return 1
    print("\n 4/4 Starting the bot")
    if dry:
        print("     (dry run: would set NINJATRADER_LIVE, start the server, start the bot)")
        return 0
    bad = arm_problem(cfg)
    if bad:
        print(f" [FIX] {bad}. Nothing is armed.")
        return 1
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
        print(' [FIX] The server did not start in 2 minutes. Look at the "Liquidity Engine bot" window.')
        return 1
    rb = arm_b(cfg["atlas"])
    print(f"     25K (ATLAS): {'armed' if rb.get('ok') else 'NOT armed: ' + str(rb.get('error'))[:160]}")
    from . import ninjatrader
    wm = ["--write-mode", cfg["write_mode"]] if cfg.get("write_mode") else []
    rc = ninjatrader.main(["--start", "--account", cfg["lit"], "--confirm", phrase, *wm])
    if rc:
        print(" [FIX] The bot did not start (see the lines above). Send Claude a photo of this window.")
        return 1
    probs = verify_routes(cfg["lit"], cfg["atlas"])
    if probs:
        print(" [STOP] Wrong account set-up: " + "; ".join(probs) + ". Stopping the bot (nothing traded).")
        ninjatrader.main(["--stop"])
        return 1
    print(f"\n [OK] Zlarior trades the 50K {cfg['lit']} · ATLAS trades the 25K {cfg['atlas']} (checked in the running bot)")
    ninjatrader.main(["--enable-auto-resume", "--account", cfg["lit"], "--confirm", phrase, *wm])
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
    return 0


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
    print("     Check both names against NinjaTrader's Accounts tab (50K about $49,700, 25K about $25,000).")
    print("     Typing the line also lets the bot come back by itself after a restart (PC on + NinjaTrader connected);")
    print("     the kill switch or STOP BOT turns that off.")
    phrase = typed_phrase(ask(" Type  I ACCEPT LIVE RISK  then Enter (anything else stops here, nothing armed)", None, inp))
    return step_arm(cfg, phrase, dry)


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
    for e in (_extras() if extras is None else extras):
        if str(e.get("nt_account") or "").strip() == name:
            return f"the funded account {e.get('id')}" if e.get("mode") == "funded" else f"the extra Zlarior account {e.get('id')}"
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
    run_bad = running and (probs or names_bad)
    steps = [
        {"key": "nt", "label": "NinjaTrader connected", "done": nt is True, "action": "nt", "button": "Open NinjaTrader",
         "needs": [], "detail": "connected" if nt is True else
         "not connected: log in to NinjaTrader and connect your MFFU account" if nt is False else
         "not seen: open NinjaTrader and log in"},
        {"key": "feed", "label": "Live bars from NinjaTrader", "done": bars is None, "action": "recheck", "button": "Check again",
         "needs": [], "detail": "LE_BarFeed's MNQ 5-minute bars are fresh" if bars is None else f"{bars}: {FEED_FIX}"},
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
        {"key": "armed", "label": "Armed", "done": not arm_miss, "action": "arm", "button": "Arm and start",
         "needs": ["nt", "feed", "accounts", "setup", "sims"],
         "detail": "live switch on, 25K armed" if not arm_miss else "; ".join(arm_miss) + " (you type I ACCEPT LIVE RISK)"},
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
                      ("running" if not run_bad else "running, wrong set-up") if running else "stopped"])
    why = None if running else resume_problem(cfg, b=b, live=live)
    return {"steps": steps, "all_green": all(done.values()), "say": say, "lit": lit or None, "atlas": atlas or None,
            "suggest_lit": (_read(AUTOSTART).get("nt_account") or "").strip() or None, "running": running,
            "market_open": market_open(), "job": job_status(), "phrase": LIVE_PHRASE,
            "need_phrase": bool(not running and why), "resume_why": why}


# ---------------------------------------------------------------------------- one button: "Start trading"
# The Start page's big button runs every step in order in one job (`python -m engine.go --step auto`, step_auto below):
# update if behind, NinjaTrader open + connected, live bars, the Sim test (once), then the start. The start needs no typed
# phrase when the owner's auto-resume opt-in is valid for exactly the 50K (he typed I ACCEPT LIVE RISK for it; the kill
# switch clears it): then it is the same gate as the auto-resume after a reboot (engine/autoresume.decide), run in the
# server (resume_now). Otherwise the page asks for the phrase once and the job runs step_arm with it.
AUTO_WAIT_S = 20 * 60          # NinjaTrader log-in / live bars: the job waits this long, re-checking
NT_EVERY_S, FEED_EVERY_S = 10, 15
CLOCK_MAX_S = 5.0
CLOCK_STEPS = ("On the PC: Windows Settings > Time & language > Date & time: turn on \"Set time automatically\", "
               "then press \"Sync now\".")


def resume_problem(cfg=None, optin=None, b=None, live=None) -> str | None:
    """Why "Start trading" needs the typed phrase (None = it does not): the auto-resume opt-in (data/auto_resume.json, made
    when the owner typed I ACCEPT LIVE RISK at a start) valid for exactly the saved 50K, the live switch on, ATLAS's 25K
    armed."""
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
    return None


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
    return {"ok": True, "say": f"Running: Zlarior → 50K {cfg['lit']} · ATLAS → 25K {cfg['atlas']}",
            "refused_accounts": d.get("refused_accounts") or []}


def sync_clock(run=None) -> dict:
    """The Start page's "Sync the clock": `w32tm /resync` (Windows' own time service). It may need an administrator: then
    the Windows Settings steps instead."""
    if os.name != "nt" and run is None:
        return {"ok": False, "error": "Only on the Windows PC.", "steps": CLOCK_STEPS}
    run = run or subprocess.run
    try:
        r = run(["w32tm", "/resync"], capture_output=True, text=True, timeout=40)
        out, code = (r.stdout or "") + (r.stderr or ""), r.returncode
    except Exception as e:
        out, code = f"{e.__class__.__name__}: {e}", 1
    low = out.lower()
    if code == 0 and "error" not in low and "denied" not in low and "not been started" not in low:
        return {"ok": True, "say": "Clock synced with internet time.", "out": out.strip()[-200:]}
    why = ("Windows asks for an administrator to sync the clock" if "denied" in low or "0x80070005" in low else
           "Windows' time service is off" if "not been started" in low or "0x80070426" in low else
           "Windows did not sync the clock")
    return {"ok": False, "error": f"{why}. {CLOCK_STEPS}", "steps": CLOCK_STEPS, "out": out.strip()[-200:]}


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
        _note("running", "Already running." if not probs else "Running with the wrong set-up: " + "; ".join(probs),
              need=None if not probs else "stop")
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
        if time.time() - t0 > wait_s:
            _note("feed", f"Still no live bars from NinjaTrader ({why}). In NinjaTrader: {FEED_FIX}. The page tries again by itself.",
                  retry_s=60)
            return 1
        _note("feed", f"No live bars from NinjaTrader ({why}). In NinjaTrader: {FEED_FIX}. Checking again every 15 s.",
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
        _note("running", f"Running: Zlarior → 50K {lit} · ATLAS → 25K {atlas}.")
        return 0
    if phrase != LIVE_PHRASE:
        _note("arm", f"Type I ACCEPT LIVE RISK once to arm both accounts ({why}).", need="phrase")
        return 3
    _note("arm", "Arming and starting: Zlarior → 50K, ATLAS → 25K")
    rc = step_arm(cfg, phrase, open_page=False)
    if rc:
        _note("arm", "Arming did not finish (see the lines below). Press Start trading to try again.")
        return rc
    _note("running", f"Running: Zlarior → 50K {lit} · ATLAS → 25K {atlas}.")
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
    if strategy not in ("zlarior", "atlas"):
        return {"ok": False, "error": "Pick the bot: Zlarior or ATLAS."}
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
    import re
    from . import multi_account as ma
    base = re.sub(r"[^A-Za-z0-9_-]", "", name)[:32] or "acct"
    ids = {str(e.get("id")) for e in _extras()}
    ident = next(x for x in (base if i == 0 else f"{base}-{i}" for i in range(100)) if x not in ids)
    rc, lines = _quiet(ma.main, ["--add", "--id", ident, "--name", label, "--nt-account", name, "--preset", preset, "--mode",
                                 "two_week", "--eval-start", start, "--adapter", "ninjatrader", "--file", _accounts_path()])
    if rc:
        return {"ok": False, "error": "Not added: " + (lines[-1] if lines else "see the log"), "lines": lines}
    _allow(name)
    return {"ok": True, "say": f"Zlarior also trades {name} ({label}, from {start}). Not armed: it joins at the next start.",
            "lines": lines}


def remove_account(name) -> dict:
    """Take one account off its bot (the bot stopped). The name leaves the allowlist when no bot uses it any more."""
    name = str(name or "").strip()
    cfg = _read(CFG)
    lit, atlas = _names(cfg)
    b_on = str(_b().get("account") or "").strip()
    ex = next((e for e in _extras() if name and name in (str(e.get("nt_account") or "").strip(), str(e.get("id") or ""))), None)
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
    return {"ok": True, "say": f"{funded_name} is funded ({PLANS[plan][1]}) from {start}. Not armed: it joins at the next start.",
            "lines": [ln for ln in lines if "python" not in ln]}


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
    elif feed_problem() is not None:
        return {"ok": False, "error": f"No live bars from NinjaTrader: {FEED_FIX}."}
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
    return run(dry=a.dry_run, pull=not a.no_pull)


if __name__ == "__main__":
    sys.exit(main())
