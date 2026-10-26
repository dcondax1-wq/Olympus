"""The owner's Windows scripts (the .bat icons and scripts/*.ps1) on a Surface with Windows PowerShell 5.1.

1. Static, always: every .bat has CRLF line endings, every goto / call target exists, a .bat that pulls new code runs
   from a copy (cmd.exe reads a running .bat by byte offset), .gitattributes keeps it so; every .ps1 is ASCII or UTF-8 with
   a BOM (5.1 reads BOM-less files as ANSI), and no PowerShell-7-only syntax (regex fallback when pwsh is missing).
2. With pwsh (PowerShell 7 on Linux; LE_PWSH=<path> or pwsh on PATH, else skipped): a token-level 5.1 lint
   (tests/win_harness/lint51.ps1), then each script really runs in a sandbox copy of the repo with a Windows stub layer
   (tests/win_harness/profile.ps1: powercfg, registry, ScheduledTasks, Get-NetTCPConnection, UAC Start-Process,
   WScript.Shell, Read-Host with scripted answers; fake git / python / powershell.exe in tests/win_harness/*.sh). The real
   server.py starts under scripts/run_bot.ps1 and scripts/stop_bot.ps1 stops it through the real /api/live/stop.
   Every flow must reach its end with [OK] lines and no PowerShell error; runs once more under Set-StrictMode -Version 2.

Nothing touches the real machine: no real git, no NinjaTrader, no orders, no phrase (a dummy text stands in for it).

  python -X utf8 -m tests.test_win_scripts            (about 1-2 min with pwsh)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARN = os.path.join(ROOT, "tests", "win_harness")
RES = []

BATS = ["ONE_TIME_SETUP.bat", "UPDATE.bat", "HEALTH_CHECK.bat", "START_DASHBOARD.bat", "STOP_BOT.bat", "SETUP_SHORTCUTS.bat"]
PS1 = ["one_time_setup.ps1", "run_bot.ps1", "stop_bot.ps1", "make_shortcuts.ps1", "install_ops_task.ps1",
       "install_autostart.ps1", "setup_dedicated_pc.ps1", "uninstall_autostart.ps1", "status.ps1", "schedule_pc.ps1",
       "schedule_pc_run.ps1"]
ADMIN_EXPR = ("([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole("
              "[Security.Principal.WindowsBuiltInRole]::Administrator)")
DUMMY_PHRASE ="dummy words for the harness"          # not the live phrase; the fake python never forwards it anywhere


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:900]})" if detail and not cond else ""))
    return bool(cond)


def rb(rel):
    with open(os.path.join(ROOT, rel), "rb") as fh:
        return fh.read()


# ============================================================================================== static: .bat
def lint_bat(name: str, raw: bytes) -> list[str]:
    out = []
    if b"\n" in raw.replace(b"\r\n", b""):
        out.append("LF-only line endings (cmd.exe misreads labels / goto in LF files)")
    if not raw.endswith(b"\r\n"):
        out.append("last line has no CRLF")
    try:
        txt = raw.decode("ascii")
    except UnicodeDecodeError:
        out.append("non-ASCII bytes (cmd.exe reads the OEM code page)")
        txt = raw.decode("utf-8", "replace")
    lines = txt.split("\r\n")
    labels = {ln.strip()[1:].split()[0].lower() for ln in lines if ln.strip().startswith(":") and not ln.strip().startswith("::")}
    labels.add("eof")
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if s.lower().startswith("rem") or s.startswith("::"):
            continue
        for m in re.finditer(r"(?i)\b(?:goto|call)\s+:([A-Za-z0-9_]+)", s):
            if m.group(1).lower() not in labels:
                out.append(f"line {i}: target :{m.group(1)} does not exist")
        for m in re.finditer(r'"%~dp0([^"]+)"', s):
            p = m.group(1).replace("\\", os.sep)
            if "%" not in p and not os.path.exists(os.path.join(ROOT, p)):
                out.append(f"line {i}: {m.group(1)} does not exist in the repo")
        if s.count("(") != s.count(")") and not s.lower().startswith("echo"):
            out.append(f"line {i}: unbalanced parentheses")
        if re.search(r"(?i)\bpowershell\b", s) and "-File" in s and "-ExecutionPolicy Bypass" not in s:
            out.append(f"line {i}: powershell -File without -ExecutionPolicy Bypass (blocked by the default policy)")
    return out


def static_bats():
    ga = rb(".gitattributes").decode()
    check(".gitattributes forces CRLF for *.bat and *.cmd", re.search(r"^\*\.bat\s+text\s+eol=crlf", ga, re.M)
          and re.search(r"^\*\.cmd\s+text\s+eol=crlf", ga, re.M), ga)
    for b in BATS:
        probs = lint_bat(b, rb(b))
        check(f"{b}: CRLF, ASCII, labels and paths exist", not probs, probs)
    upd = rb("UPDATE.bat").decode()
    # cmd.exe reads a running .bat by byte offset: git pull rewriting UPDATE.bat mid-run makes it run garbage
    check("UPDATE.bat runs from a temp copy before git pull (a pulled UPDATE.bat cannot derail the running one)",
          re.search(r'(?im)^copy\s+/y\s+"%~f0"\s+"%TEMP%[^\r\n]*\r\ncall\s+"%TEMP%[^\r\n]*&\s*exit\s+/b', upd)
          and re.search(r"(?im)^if /i \"%~1\"==\"--from-temp\" goto :main", upd)
          and upd.index("--from-temp") < upd.index("-m engine.autoupdate --pull")
          and "%~dp0scripts" not in upd, "")
    one = rb("ONE_TIME_SETUP.bat").decode()
    run_line = [ln for ln in one.split("\r\n") if "one_time_setup.ps1" in ln and ln.strip().lower().startswith("powershell")]
    check("ONE_TIME_SETUP.bat: the PowerShell line and its pause / exit are one parsed line (the setup pulls a new .bat)",
          run_line and "& pause" in run_line[0].lower() and "exit /b" in run_line[0].lower(), run_line)


# ============================================================================================== static: .ps1
PS7_REGEX = [
    (r"\?\?", "'??' operator"), (r"\?\.(?=[A-Za-z_])", "'?.' operator"), (r"(?<![|&])(&&|\|\|)(?![|&])", "&& / || chain"),
    (r"-AsHashtable", "ConvertFrom-Json -AsHashtable"), (r"ForEach-Object\s+-Parallel", "ForEach-Object -Parallel"),
    (r"(?i)-Encoding\s+['\"]?utf8NoBOM", "-Encoding utf8NoBOM"), (r"\$PSStyle", "$PSStyle"),
]


def strip_ps_strings(code: str) -> str:
    code = re.sub(r"<#.*?#>", "", code, flags=re.S)
    code = re.sub(r"'[^'\n]*'", "''", code)
    code = re.sub(r'"(?:`.|[^"`\n])*"', '""', code)
    return "\n".join(ln.split("#", 1)[0] for ln in code.splitlines())


def static_ps1(pwsh: str | None):
    files = [os.path.join(ROOT, "scripts", f) for f in PS1 if os.path.exists(os.path.join(ROOT, "scripts", f))]
    for f in files:
        raw = open(f, "rb").read()
        bom = raw.startswith(b"\xef\xbb\xbf")
        try:
            raw.decode("ascii")
            ascii_ok = True
        except UnicodeDecodeError:
            ascii_ok = False
        check(f"{os.path.basename(f)}: ASCII or UTF-8 with BOM (5.1 reads a BOM-less file as ANSI)", ascii_ok or bom,
              [i for i, ln in enumerate(raw.split(b"\n"), 1) if any(c > 127 for c in ln)][:10])
        code = strip_ps_strings(raw.decode("utf-8", "replace"))
        hits = [(n, i) for i, ln in enumerate(code.splitlines(), 1) for rx, n in PS7_REGEX if re.search(rx, ln)]
        check(f"{os.path.basename(f)}: no PowerShell 7 syntax (regex)", not hits, hits)
        # 5.1 prints a native tool's stderr (git progress, pip warnings) piped straight to Out-Host as red
        # "NativeCommandError" blocks that look like failures: turn the records into plain text first
        red = [i for i, ln in enumerate(code.splitlines(), 1) if re.search(r"2>&1\s*\|\s*Out-Host", ln)]
        check(f"{os.path.basename(f)}: no '2>&1 | Out-Host' (red NativeCommandError text on 5.1)", not red, red)
        if ADMIN_EXPR in raw.decode("utf-8", "replace"):
            check(f"{os.path.basename(f)}: the Administrator test is inside try (it throws off Windows / in odd hosts)",
                  re.search(r"try\s*\{\s*\$isAdmin\s*=\s*\[bool\]" + re.escape(ADMIN_EXPR), raw.decode()), "")
    if not pwsh:
        print("[SKIP] token-level 5.1 lint: pwsh not found (set LE_PWSH or install PowerShell 7)")
        return
    r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-File", os.path.join(HARN, "lint51.ps1"), *files],
                       capture_output=True, text=True, timeout=120)
    found = [ln for ln in r.stdout.splitlines() if ln.strip()]
    check("5.1 lint (PowerShell parser tokens + AST): no 7-only syntax, cmdlet parameters or encodings", r.returncode == 0 and not found,
          found or r.stderr)


# ============================================================================================== dynamic: sandbox
def find_pwsh() -> str | None:
    p = os.environ.get("LE_PWSH") or shutil.which("pwsh")
    return p if p and os.path.exists(p) else None


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Sandbox:
    def __init__(self, pwsh: str, strict: bool = False):
        self.pwsh, self.strict = pwsh, strict
        self.dir = tempfile.mkdtemp(prefix="le_win_")
        self.repo = os.path.join(self.dir, "repo")
        skip = {".git", "research", "cache", "reports", "snapshot", "tests", "__pycache__", "logs", "backups", "node_modules"}
        shutil.copytree(ROOT, self.repo, ignore=lambda d, names: [n for n in names if (d == ROOT and n in skip) or n in
                                                                  ("__pycache__", "node_modules", ".pytest_cache")])
        os.makedirs(os.path.join(self.repo, "research"), exist_ok=True)
        # the only Windows-only .NET calls (no PowerShell stub can replace a static .NET method): the Administrator test
        # reads LE_T_ELEVATED (set by the UAC stub, or "1" for an Administrator PowerShell); a fixed C:\ drive path
        for f in os.listdir(os.path.join(self.repo, "scripts")):
            if f.endswith(".ps1"):
                p = os.path.join(self.repo, "scripts", f)
                s = open(p, encoding="utf-8-sig").read()
                s2 = s.replace(ADMIN_EXPR, "($env:LE_T_ELEVATED -eq '1')").replace("'C:\\Program Files'", "$env:ProgramFiles")
                if s2 != s:
                    open(p, "w", encoding="utf-8").write(s2)
        for sub in ("bin", "git", "tasks", "bg", "home/.config/powershell", "home/Desktop",
                    "appdata/Microsoft/Windows/Start Menu/Programs/Startup", "pf/NinjaTrader 8/bin",
                    "win/System32/WindowsPowerShell/v1.0"):
            os.makedirs(os.path.join(self.dir, sub), exist_ok=True)
        cp = lambda src, dst: (shutil.copy(os.path.join(HARN, src), os.path.join(self.dir, dst)), os.chmod(os.path.join(self.dir, dst), 0o755))
        cp("powershell.sh", "bin/powershell")
        cp("powershell.sh", "win/System32/WindowsPowerShell/v1.0/powershell.exe")
        cp("python.sh", "bin/python")
        cp("git.sh", "bin/git")
        shutil.copy(os.path.join(HARN, "profile.ps1"), os.path.join(self.dir, "home/.config/powershell/profile.ps1"))
        open(os.path.join(self.dir, "pf/NinjaTrader 8/bin/NinjaTrader.exe"), "w").close()
        open(os.path.join(self.dir, "git/branch"), "w").write("main\n")
        self.port = free_port()
        self.log = os.path.join(self.dir, "calls.log")
        open(self.log, "w").close()
        self.env = {
            "PATH": os.path.join(self.dir, "bin") + os.pathsep + "/usr/local/bin:/usr/bin:/bin",
            "HOME": os.path.join(self.dir, "home"), "SystemRoot": os.path.join(self.dir, "win"),
            "APPDATA": os.path.join(self.dir, "appdata"), "ProgramFiles": os.path.join(self.dir, "pf"),
            "USERDOMAIN": "SURFACE", "USERNAME": "owner", "PROCESSOR_ARCHITECTURE": "AMD64", "PORT": str(self.port), "HOST": "127.0.0.1",
            "LE_HEARTBEAT": "0", "LE_NO_AUTOSTART": "1", "LE_OPS_PUSH": "0", "PYTHONDONTWRITEBYTECODE": "1",
            "LE_T_LOG": self.log, "LE_T_REG": os.path.join(self.dir, "registry.json"),
            "LE_T_TASKS": os.path.join(self.dir, "tasks"), "LE_T_BG": os.path.join(self.dir, "bg"),
            "LE_T_GIT": os.path.join(self.dir, "git"), "LE_T_ANSWERS": os.path.join(self.dir, "answers.json"),
            "LE_T_PWSH": pwsh, "LE_T_PYREAL": sys.executable, "LE_T_PORTPID": os.path.join(HARN, "portpid.py"),
            "LE_T_STRICT": "1" if strict else "0", "TERM": "dumb", "POWERSHELL_TELEMETRY_OPTOUT": "1",
            "POWERSHELL_UPDATECHECK": "Off", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        }
        for k in ("LANG", "LC_ALL", "TMPDIR"):
            if os.environ.get(k):
                self.env[k] = os.environ[k]

    def answers(self, items):
        with open(self.env["LE_T_ANSWERS"], "w") as fh:
            json.dump(list(items), fh)

    def ps(self, script: str, *args, env=None, timeout=300):
        """Like a .bat line: powershell -NoProfile -ExecutionPolicy Bypass -File <script> <args>."""
        e = {**self.env, **(env or {})}
        cmd = [os.path.join(self.dir, "bin", "powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               os.path.join(self.repo, "scripts", script), *args]
        r = subprocess.run(cmd, cwd=self.repo, env=e, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr

    def calls(self, prefix=""):
        return [ln.rstrip("\n").split("\t") for ln in open(self.log, encoding="utf-8") if ln.startswith(prefix)]

    def reg(self):
        p = self.env["LE_T_REG"]
        return json.load(open(p)) if os.path.exists(p) else {}

    def task(self, name):
        p = os.path.join(self.env["LE_T_TASKS"], f"{name}.json")
        return json.load(open(p)) if os.path.exists(p) else None

    def ping(self):
        try:
            import urllib.request
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/health/ping", timeout=2) as r:
                return json.loads(r.read().decode())
        except Exception:
            return None

    def cleanup(self):
        pids = os.path.join(self.env["LE_T_BG"], "pids.txt")
        if os.path.exists(pids):
            for ln in open(pids):
                try:
                    os.kill(int(ln.strip()), 9)
                except Exception:
                    pass
        for ln in subprocess.run([sys.executable, self.env["LE_T_PORTPID"], str(self.port)], capture_output=True,
                                 text=True).stdout.split():
            try:
                os.kill(int(ln), 9)
            except Exception:
                pass
        shutil.rmtree(self.dir, ignore_errors=True)


ERR_RX = re.compile(r"(?m)^(.*(Exception|CategoryInfo|FullyQualifiedErrorId|is not recognized|ParserError|"
                    r"Cannot bind|cannot be found|The term '|PropertyNotFoundStrict|VariableIsUndefined|"
                    r"InvalidOperation|harness: ).*)$")


def ps_errors(out: str, err: str, allow=()) -> list[str]:
    bad = [m[0] for m in ERR_RX.findall(out)] + [ln for ln in err.splitlines() if ln.strip()]
    return [ln for ln in dict.fromkeys(bad) if not any(a in ln for a in allow)]


def scenario_one_time_setup(sb: Sandbox, tag: str):
    """Enter = Sim101, UAC Yes: the full flow a-i, real server.py up under run_bot.ps1, then stop_bot.ps1."""
    sb.answers([""])                                                  # eval account: just Enter -> Sim101
    code, out, err = sb.ps("one_time_setup.ps1", "-Port", str(sb.port))
    errs = ps_errors(out, err)
    check(f"[{tag}] one_time_setup.ps1 (Enter = Sim101, UAC yes) exits 0 with no PowerShell error", code == 0 and not errs,
          f"code={code} errs={errs[:8]} tail={out[-1500:]}")
    check(f"[{tag}] ... ends ALL GREEN, no [FIX] line", "ALL GREEN" in out and not re.search(r"(?m)^\s*\[FIX\] ", out), [ln for ln in out.splitlines() if "[FIX]" in ln] or out[-1500:])
    for step in ("a. Stop the bot", "b. Power", "c. Windows Update", "d. Start at logon", "d. NinjaTrader starts", "e. Desktop icons",
                 "f. The bot updates itself", "g. Start the bot", "h. Health check", "i. Still by hand"):
        if not check(f"[{tag}] ... step '{step}' ran", step in out, out[-1500:]):
            break
    pc = [" ".join(c[1:]) for c in sb.calls("powercfg")]
    check(f"[{tag}] ... powercfg: standby / hibernate 0 on AC, lid = nothing, USB suspend off, setactive",
          all(any(x in p for p in pc) for x in ("/change standby-timeout-ac 0", "/change hibernate-timeout-ac 0",
                                                 "SUB_BUTTONS LIDACTION 0", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0",
                                                 "/setactive SCHEME_CURRENT")), pc)
    ux = sb.reg().get(r"HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings", {})
    pe = (ux.get("PauseUpdatesExpiryTime") or {}).get("value", "")
    check(f"[{tag}] ... Windows Update: active hours DWORDs, pause expiry in ISO-8601 UTC (yyyy-MM-ddTHH:mm:ssZ)",
          ux.get("ActiveHoursStart", {}).get("type") == "DWord" and ux.get("ActiveHoursEnd", {}).get("type") == "DWord"
          and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", pe or ""), ux)
    au = sb.reg().get(r"HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU", {})
    check(f"[{tag}] ... NoAutoRebootWithLoggedOnUsers = 1", (au.get("NoAutoRebootWithLoggedOnUsers") or {}).get("value") == 1, au)
    t = sb.task("LiquidityEngine")
    ok = bool(t) and t["Principal"]["UserId"] == r"SURFACE\owner" and t["Principal"]["RunLevel"] == "Limited" \
        and "run_bot.ps1" in t["Actions"][0]["Arguments"] and "-ExecutionPolicy Bypass" in t["Actions"][0]["Arguments"] \
        and t["Settings"]["ExecutionTimeLimit"] == "PT0S" and len(t["Triggers"]) == 2
    check(f"[{tag}] ... task LiquidityEngine: as the owner, not elevated, run_bot.ps1, no time limit, logon + unlock", ok, t)
    t2 = sb.task("LiquidityEngineOps")
    check(f"[{tag}] ... task LiquidityEngineOps: every 5 min + at logon, ops_tick.py", bool(t2)
          and t2["Triggers"][0]["Repetition"]["Interval"] == "PT5M" and "ops_tick.py" in t2["Actions"][0]["Arguments"], t2)
    desk = sorted(os.listdir(os.path.join(sb.dir, "home", "Desktop")))
    check(f"[{tag}] ... 4 desktop icons", desk == ["LE DASHBOARD.lnk", "LE HEALTH CHECK.lnk", "LE STOP BOT.lnk", "LE UPDATE.lnk"], desk)
    stp = os.listdir(os.path.join(sb.dir, "appdata/Microsoft/Windows/Start Menu/Programs/Startup"))
    check(f"[{tag}] ... NinjaTrader Startup shortcut", stp == ["NinjaTrader 8 (Liquidity Engine).lnk"], stp)
    py = [c[1:] for c in sb.calls("python")]
    starts = [c for c in py if "--start" in c]
    check(f"[{tag}] ... the bot was started on Sim101 only (no confirm phrase, no other account)",
          len(starts) == 1 and starts[0][starts[0].index("--account") + 1] == "Sim101" and "--confirm" not in starts[0], starts)
    check(f"[{tag}] ... the real server.py answers /api/health/ping (started by run_bot.ps1)", sb.ping() is not None, "")
    srv_log = os.path.join(sb.repo, "logs")
    check(f"[{tag}] ... run_bot.ps1 wrote logs\\supervisor.pid and a server log", os.path.exists(os.path.join(srv_log, "supervisor.pid"))
          and any(f.startswith("server-") for f in os.listdir(srv_log)), os.listdir(srv_log))
    # stop_bot.ps1: the real /api/live/stop, then server and supervisor end
    code, out, err = sb.ps("stop_bot.ps1", "-Port", str(sb.port), timeout=60)
    errs = ps_errors(out, err)
    check(f"[{tag}] stop_bot.ps1 exits 0, the API stop answered, server + supervisor gone", code == 0 and not errs
          and "bot stopped via API" in out and "stopped" in out, f"{code} {errs} {out}")
    t_end = time.time() + 15
    while sb.ping() is not None and time.time() < t_end:
        time.sleep(0.5)
    check(f"[{tag}] ... the server no longer answers", sb.ping() is None, "")
    t_end = time.time() + 15
    while os.path.exists(os.path.join(srv_log, "supervisor.pid")) and time.time() < t_end:
        time.sleep(0.5)
    check(f"[{tag}] ... the supervisor removed its pid file (exited by the stop file)", not os.path.exists(os.path.join(srv_log, "supervisor.pid")),
          open(os.path.join(srv_log, sorted(f for f in os.listdir(srv_log) if f.startswith("server-"))[-1])).read()[-1500:])


def scenario_live(sb: Sandbox):
    """An eval account name + the live switch line present + a (dummy) phrase typed hidden: --start and auto-resume."""
    with open(os.path.join(sb.repo, ".env.local.ps1"), "w") as fh:
        fh.write("# harness: NINJATRADER_LIVE is only named here, nothing is set\n")
    sb.answers(["MFFUEVAL50K123", DUMMY_PHRASE])
    code, out, err = sb.ps("one_time_setup.ps1", "-Port", str(sb.port))
    errs = ps_errors(out, err)
    check("[live] one_time_setup.ps1 with an eval account exits 0, no error, ALL GREEN", code == 0 and not errs and "ALL GREEN" in out,
          f"{code} {errs[:6]} {out[-2000:]}")
    py = [c[1:] for c in sb.calls("python")]
    st = [c for c in py if "--start" in c]
    ar = [c for c in py if "--enable-auto-resume" in c]
    check("[live] ... --start and --enable-auto-resume on the eval account with the typed phrase as ONE argument",
          len(st) == 1 and st[0][st[0].index("--account") + 1] == "MFFUEVAL50K123" and st[0][st[0].index("--confirm") + 1] == DUMMY_PHRASE
          and len(ar) == 1, st + ar)
    rh = sb.calls("Read-Host")
    check("[live] ... the phrase prompt was hidden (SecureString), never echoed to the screen", any(c[-1] == "<secure>" for c in rh)
          and DUMMY_PHRASE not in out, rh)
    logs = os.path.join(sb.repo, "logs")
    leaked = [f for f in os.listdir(logs) if os.path.isfile(os.path.join(logs, f)) and DUMMY_PHRASE in open(os.path.join(logs, f), errors="replace").read()]
    check("[live] ... the phrase is in no log file", not leaked, leaked)
    sb.ps("stop_bot.ps1", "-Port", str(sb.port), timeout=60)


def scenario_uac_no(sb: Sandbox):
    """The owner clicks No on the UAC prompt: a clear [FIX], the logon tasks are tried without elevation."""
    sb.answers([""])
    code, out, err = sb.ps("one_time_setup.ps1", "-Port", str(sb.port), env={"LE_T_UAC": "no"})
    errs = ps_errors(out, err)
    check("[uac-no] exits 0, no PowerShell error, [FIX] 'No Administrator rights', tasks still made", code == 0 and not errs
          and "No Administrator rights" in out and sb.task("LiquidityEngine") and sb.task("LiquidityEngineOps")
          and not sb.calls("powercfg"), f"{code} {errs[:6]} {out[-2000:]}")
    sb.ps("stop_bot.ps1", "-Port", str(sb.port), timeout=60)


def scenario_admin(sb: Sandbox):
    """ONE_TIME_SETUP started from an Administrator window: no UAC prompt, the admin part runs in place."""
    sb.answers([""])
    code, out, err = sb.ps("one_time_setup.ps1", "-Port", str(sb.port), env={"LE_T_ELEVATED": "1"})
    errs = ps_errors(out, err)
    check("[admin] already Administrator: exits 0, ALL GREEN, no UAC Start-Process, tasks for the owner", code == 0 and not errs
          and "ALL GREEN" in out and not [c for c in sb.calls("Start-Process") if "verb=RunAs" in c]
          and (sb.task("LiquidityEngine") or {}).get("Principal", {}).get("UserId") == r"SURFACE\owner", f"{code} {errs[:6]} {out[-1500:]}")
    sb.ps("stop_bot.ps1", "-Port", str(sb.port), timeout=60)


def scenario_small(sb: Sandbox):
    open(sb.log, "w").close()
    for f in os.listdir(sb.env["LE_T_TASKS"]):
        os.remove(os.path.join(sb.env["LE_T_TASKS"], f))
    code, out, err = sb.ps("one_time_setup.ps1", "-DryRun")
    check("[dry] one_time_setup.ps1 -DryRun exits 0, no error, changes nothing", code == 0 and not ps_errors(out, err)
          and "DRY RUN" in out and not sb.calls("powercfg") and not sb.task("LiquidityEngine"), f"{code} {err} {out}")
    for script, args in (("run_bot.ps1", ["-DryRun"]), ("stop_bot.ps1", ["-DryRun"]), ("install_autostart.ps1", ["-DryRun"]),
                         ("install_ops_task.ps1", ["-DryRun"]), ("make_shortcuts.ps1", ["-DryRun"]),
                         ("setup_dedicated_pc.ps1", ["-DryRun"]), ("status.ps1", [])):
        code, out, err = sb.ps(script, *args, timeout=120)
        errs = ps_errors(out, err)
        check(f"[dry] {script} {' '.join(args)} exits 0, no PowerShell error", code == 0 and not errs, f"{code} {errs[:6]} {out[-800:]}")
    # the SETUP_SHORTCUTS.bat pair, for real, twice (the second run replaces what the first made)
    for i in (1, 2):
        c1, o1, e1 = sb.ps("make_shortcuts.ps1")
        c2, o2, e2 = sb.ps("install_ops_task.ps1")
        check(f"[shortcuts run {i}] make_shortcuts + install_ops_task exit 0, 4 icons + the helper task", c1 == 0 and c2 == 0
              and not ps_errors(o1, e1) and not ps_errors(o2, e2) and o1.count("[OK]") == 4 and sb.task("LiquidityEngineOps"),
              f"{c1} {c2} {ps_errors(o1, e1)} {ps_errors(o2, e2)} {o1} {o2}")
    c, o, e = sb.ps("install_autostart.ps1", "-Port", str(sb.port))
    c2, o2, e2 = sb.ps("install_autostart.ps1", "-Port", str(sb.port))
    check("[autostart] install_autostart.ps1 twice exits 0 (replaces the task)", c == 0 and c2 == 0 and not ps_errors(o2, e2)
          and "replacing it" in o2, f"{c} {c2} {ps_errors(o, e)} {ps_errors(o2, e2)} {o2}")
    c, o, e = sb.ps("uninstall_autostart.ps1")
    check("[autostart] uninstall_autostart.ps1 removes it", c == 0 and not sb.task("LiquidityEngine"), f"{c} {o} {e}")
    c, o, e = sb.ps("install_ops_task.ps1", "-Remove")
    check("[ops] install_ops_task.ps1 -Remove", c == 0 and not sb.task("LiquidityEngineOps") and not ps_errors(o, e), f"{c} {o} {e}")
    # an Administrator PowerShell running setup_dedicated_pc.ps1 for real
    c, o, e = sb.ps("setup_dedicated_pc.ps1", "-NinjaTrader", os.path.join(sb.dir, "pf/NinjaTrader 8/bin/NinjaTrader.exe"), "-Port", str(sb.port),
                    env={"LE_T_ELEVATED": "1"})
    check("[dedicated] setup_dedicated_pc.ps1 (Administrator) exits 0, no error, power + logon task + NinjaTrader shortcut", c == 0
          and not ps_errors(o, e) and sb.task("LiquidityEngine") and sb.calls("powercfg")
          and os.listdir(os.path.join(sb.dir, "appdata/Microsoft/Windows/Start Menu/Programs/Startup")), f"{c} {ps_errors(o, e)} {o[-1500:]}")
    # the branch guard: a hand-edited branch is never switched
    open(os.path.join(sb.dir, "git/branch"), "w").write("claude/x\n")
    open(os.path.join(sb.dir, "git/dirty"), "w").write(" M engine/x.py\n")
    sb.answers([])
    c, o, e = sb.ps("one_time_setup.ps1", "-Port", str(sb.port))
    check("[branch] on another branch with local edits: stops with a [FIX], exit 1, no checkout", c == 1 and "[FIX]" in o
          and not [x for x in sb.calls("git") if "checkout" in x] and not ps_errors(o, e), f"{c} {o[-1000:]} {e}")
    os.remove(os.path.join(sb.dir, "git/dirty"))


def run_dynamic(pwsh: str, strict: bool):
    tag = "strict" if strict else "5.1-like"
    sb = Sandbox(pwsh, strict=strict)
    try:
        scenario_one_time_setup(sb, tag)
        if not strict:
            sb2 = Sandbox(pwsh)
            try:
                scenario_live(sb2)
            finally:
                sb2.cleanup()
            for fn in (scenario_uac_no, scenario_admin):
                sb3 = Sandbox(pwsh)
                try:
                    fn(sb3)
                finally:
                    sb3.cleanup()
        scenario_small(sb)
    finally:
        sb.cleanup()


def main() -> int:
    static_bats()
    pwsh = find_pwsh()
    static_ps1(pwsh)
    if pwsh:
        run_dynamic(pwsh, strict=False)
        run_dynamic(pwsh, strict=True)
    else:
        print("[SKIP] dynamic Windows-script runs: pwsh not found (set LE_PWSH=<path to pwsh> or install PowerShell 7)")
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def test_win_scripts():                      # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
