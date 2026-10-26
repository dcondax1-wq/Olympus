"""START BOT: the one double-click start for the owner (START_BOT.bat / the "LE START BOT" desktop icon).

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
"""
import argparse
import datetime as dt
import json
import os
import subprocess
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
        try:
            from . import broker_balance
            balances = {n: r.get("netliq") or r.get("cash") for n, r in (broker_balance.read().get("rows") or {}).items()
                        if r.get("fresh")}
        except Exception:
            balances = {}
    b50, b25 = balances.get(lit), balances.get(atlas)
    if b50 is not None and float(b50) < 35000:
        return f"{lit} has ${float(b50):,.0f} in NinjaTrader: that is not the 50K"
    if b25 is not None and float(b25) > 35000:
        return f"{atlas} has ${float(b25):,.0f} in NinjaTrader: that is not the 25K"
    return None


def verify_routes(lit, atlas, state=None, b=None) -> list:
    """After the start: the problems with who trades where ([] = Zlarior on the 50K, ATLAS armed on the 25K)."""
    from . import second
    if state is None:
        try:
            state = _http("/api/live/state")
        except Exception as e:
            return [f"bot state not readable ({e.__class__.__name__})"]
    b = second.load_cfg().get("account_b") if b is None else b
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


def update(py=sys.executable) -> bool:
    """git pull main (fast-forward only) while the bot is stopped; True = new code arrived (START BOT re-runs itself)."""
    import glob
    import shutil
    git = shutil.which("git") or next(iter(glob.glob(os.path.expandvars(r"%ProgramFiles%\Git\cmd\git.exe"))
                                           + glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\GitHubDesktop\app-*\resources\app\git\cmd\git.exe"))), None)
    if not git:
        print(" [..] Update skipped (git not found); starting the version on this PC.")
        return False

    def head():
        return subprocess.run([git, "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    try:
        before = head()
        r = subprocess.run([git, "pull", "--ff-only", "-q", "origin", "main"], cwd=ROOT, capture_output=True, text=True)
    except OSError:
        print(" [..] Update skipped (git did not run); starting the version on this PC.")
        return False
    if r.returncode:
        print(" [..] Update skipped (git pull did not fast-forward); starting the version on this PC.")
        return False
    return head() != before


def shortcut():
    """The "LE START BOT" desktop icon (scripts/make_shortcuts.ps1, Windows only; replaces the icons it made before)."""
    if os.name == "nt":
        subprocess.run(_ps(os.path.join(ROOT, "scripts", "make_shortcuts.ps1")), cwd=ROOT, capture_output=True)


def run(dry=False, inp=input, py=sys.executable, pull=True) -> int:
    print("\n ==== Zlarior + ATLAS: START BOT ====\n")
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

    # 1. launch prep, once
    if not cfg.get("prepped"):
        print("\n 1/4 Setting up both accounts (allowlist, 50K balance and floor, ATLAS on the 25K)")
        if dry:
            print("     (dry run: would run engine.launch_prep)")
        else:
            from . import launch_prep
            if launch_prep.main(["--atlas", cfg["atlas"], "--lit", cfg["lit"], "--atlas-start", session_day()]):
                print(" [FIX] Setup failed (see above). Send Claude a photo of this window.")
                return 1
            cfg["prepped"] = dt.date.today().isoformat()
            _save(cfg)
    else:
        print(f"\n 1/4 Accounts already set up ({cfg['prepped']})")

    # NinjaTrader open and connected (everything after needs it)
    print("\n     NinjaTrader")
    if not dry and not ensure_ninjatrader():
        print(" [FIX] NinjaTrader is not connected. Log in to NinjaTrader, then double-click START BOT again.")
        return 1

    # 2. Sim roundtrips, until both passed once
    sp = sims_passed()
    if not all(sp.values()):
        print("\n 2/4 NinjaTrader Sim101 test (a 1-micro test order on Sim101, about 1 minute)")
        if not market_open():
            print(" [WAIT] The market is closed (open Sun 18:00 ET - Fri 17:00 ET, not 17:00-18:00).")
            print("        Double-click START BOT again after it opens.")
            return 1
        if not dry and not ensure_feed():
            print(" [FIX] Still no live bars from the MNQ chart. Send Claude a photo of the chart and this window.")
            return 1
        if server_up() and not dry:
            stop_server()                                   # the roundtrip needs the bot stopped
        for kind, flag in (("roundtrip", "--sim-roundtrip"), ("add", "--sim-roundtrip-add")):
            if sp[kind]:
                continue
            if dry:
                print(f"     (dry run: would run engine.ninjatrader {flag})")
                continue
            rc = subprocess.run([py, "-X", "utf8", "-m", "engine.ninjatrader", flag], cwd=ROOT).returncode
            if rc:
                print("     Trying once more in 30 seconds (NinjaTrader can be slow right after a chart loads)")
                time.sleep(30)
                rc = subprocess.run([py, "-X", "utf8", "-m", "engine.ninjatrader", flag], cwd=ROOT).returncode
            if rc:
                print(" [FIX] The Sim test failed. Nothing is armed. Close NinjaTrader, open it again, log in, then run START BOT")
                print("       again. Still failing: send Claude a photo of this window.")
                return 1
    else:
        print("\n 2/4 Sim101 test already passed")

    # 3. the owner arms (typed, never by the bot)
    print("\n 3/4 Real money:")
    print(f"       Zlarior (LIT)  ->  50K  {cfg['lit']}")
    print(f"       ATLAS          ->  25K  {cfg['atlas']}")
    print("     Check both names against NinjaTrader's Accounts tab (50K about $49,700, 25K about $25,000).")
    print("     Typing the line also lets the bot come back by itself after a restart (PC on + NinjaTrader connected);")
    print("     the kill switch or STOP BOT turns that off.")
    phrase = ask(" Type  I ACCEPT LIVE RISK  then Enter (anything else stops here, nothing armed)", None, inp)
    if phrase != "I ACCEPT LIVE RISK":
        print(" Stopped. Nothing is armed.")
        return 1

    # 4. server with the live lock, then start
    print("\n 4/4 Starting the bot")
    if dry:
        print("     (dry run: would set NINJATRADER_LIVE, start the server, start the bot)")
        return 0
    added = False
    if not env_has_live():
        add_env_live()
        added = True
    if server_up() and (added or env_newer_than_server()):
        print("     restarting the bot server so it reads the live switch")
        stop_server()
    if not server_up() and not start_server():
        print(' [FIX] The server did not start in 2 minutes. Look at the "Liquidity Engine bot" window.')
        return 1
    rb = arm_b(cfg["atlas"])
    print(f"     25K (ATLAS): {'armed' if rb.get('ok') else 'NOT armed: ' + str(rb.get('error'))[:160]}")
    from . import ninjatrader
    rc = ninjatrader.main(["--start", "--account", cfg["lit"], "--confirm", phrase])
    if rc:
        print(" [FIX] The bot did not start (see the lines above). Send Claude a photo of this window.")
        return 1
    probs = verify_routes(cfg["lit"], cfg["atlas"])
    if probs:
        print(" [STOP] Wrong account set-up: " + "; ".join(probs) + ". Stopping the bot (nothing traded).")
        ninjatrader.main(["--stop"])
        return 1
    print(f"\n [OK] Zlarior trades the 50K {cfg['lit']} · ATLAS trades the 25K {cfg['atlas']} (checked in the running bot)")
    ninjatrader.main(["--enable-auto-resume", "--account", cfg["lit"], "--confirm", phrase])
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
    _open()
    shortcut()
    return 0


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
    a = ap.parse_args(argv)
    return run(dry=a.dry_run, pull=not a.no_pull)


if __name__ == "__main__":
    sys.exit(main())
