"""CLEAN_STORAGE.bat + scripts/clean_storage.ps1 (owner 2026-11-04: "an easy way to clear storage through both of my computers").

1. Static, always: the .bat (CRLF, ASCII, local script first, site download when it is alone), the site copies in
   tools/web_public/pc/ identical to the repo files, the script is ASCII, no PowerShell-7 syntax, only three places delete,
   no process is stopped, nothing is downloaded, the never-touch list is there; the health `storage` line (engine/pc_health).
2. With pwsh (PowerShell 7 on Linux; LE_PWSH=<path> or pwsh on PATH, else skipped): a token-level 5.1 lint, then the real
   script runs in a SANDBOX TREE (a fake Windows: Temp, browser caches, NinjaTrader 8 folder, the bot folder with its state
   files, Windows\\ junk, Windows.old). File deletes are real but only inside that tree; services / Recycle Bin / takeown /
   UAC are stubs (tests/win_harness/clean_storage_stubs.ps1; the UAC stub really runs the elevated child).
     - -DryRun: the table, nothing deleted (every file and its time unchanged), a log
     - a full run: old junk gone, EVERY protected file still there (state, .env.local.ps1, accounts, journals, nt_bars,
       NinjaTrader workspaces / templates / bin / db / le_feed / incoming / outgoing), the newest 3 backups stay,
       "Freed X, C: now Y free"
     - NinjaTrader running (a real process named NinjaTrader) or the bot answering on its port: their folders and
       Windows.old are skipped, temp / caches / Windows still cleaned, and it says so
     - a hostile TEMP (the user profile, the bot folder, the bot's data folder, NinjaTrader's workspaces / db): nothing
       protected is deleted
     - Surface without a bot folder, UAC declined, StrictMode 2

  python -X utf8 -m tests.test_clean_storage          (about 1 min with pwsh)
"""
from __future__ import annotations

import hashlib
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
PS1 = os.path.join(ROOT, "scripts", "clean_storage.ps1")
BAT = os.path.join(ROOT, "CLEAN_STORAGE.bat")
WEB = os.path.join(ROOT, "tools", "web_public", "pc")
STUBS = os.path.join(HARN, "clean_storage_stubs.ps1")
ADMIN_EXPR = ("([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole("
              "[Security.Principal.WindowsBuiltInRole]::Administrator)")
RES: list[bool] = []
DAY = 86400


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:1500]})" if detail and not cond else ""))
    return bool(cond)


def rb(path):
    with open(path, "rb") as fh:
        return fh.read()


# ============================================================================================== static
def static():
    bat = rb(BAT)
    check("CLEAN_STORAGE.bat: CRLF line endings, ASCII", b"\n" not in bat.replace(b"\r\n", b"") and bat.endswith(b"\r\n")
          and all(c < 128 for c in bat))
    check("CLEAN_STORAGE.bat: runs scripts\\clean_storage.ps1 first and pauses on the same line (the cleaner never pulls itself)",
          re.search(rb'if exist "%~dp0scripts\\clean_storage\.ps1" goto :local', bat)
          and re.search(rb'-ExecutionPolicy Bypass -File "%~dp0scripts\\clean_storage\.ps1" %\* & echo\. & pause & exit /b', bat) is not None)
    check("CLEAN_STORAGE.bat: alone (downloaded from the site) it fetches pc/clean_storage.ps1 with -UseBasicParsing and runs it",
          b"https://demetrades2000-coder.github.io/nq-dashboard/pc/clean_storage.ps1" in bat and b"-UseBasicParsing" in bat
          and bat.count(b"-ExecutionPolicy Bypass") == 3)
    check("site copy tools/web_public/pc/CLEAN_STORAGE.bat is the same file as CLEAN_STORAGE.bat",
          os.path.exists(os.path.join(WEB, "CLEAN_STORAGE.bat")) and rb(os.path.join(WEB, "CLEAN_STORAGE.bat")) == bat)
    check("site copy tools/web_public/pc/clean_storage.ps1 is the same file as scripts/clean_storage.ps1 (the build copies pc/)",
          os.path.exists(os.path.join(WEB, "clean_storage.ps1")) and rb(os.path.join(WEB, "clean_storage.ps1")) == rb(PS1))
    raw = rb(PS1)
    try:
        raw.decode("ascii")
        ok = True
    except UnicodeDecodeError:
        ok = raw.startswith(b"\xef\xbb\xbf")
    check("clean_storage.ps1: ASCII (or UTF-8 with BOM)", ok)
    code = raw.decode("utf-8", "replace")
    body = re.sub(r"<#.*?#>", "", code, flags=re.S)
    check("switches: -DryRun, -Yes, -Extras, -KeepDays (default 14), -SystemPart",
          all(re.search(r"\[switch\]\$" + s, code) for s in ("DryRun", "Yes", "Extras", "SystemPart")) and re.search(r"\[int\]\$KeepDays = 14", code))
    # the only deleting calls: one file, one empty folder, the one Windows.old tree
    dels = re.findall(r"\[System\.IO\.File\]::Delete\(|\[System\.IO\.Directory\]::Delete\(|Remove-Item", body)
    check("deletes in exactly three places (file, empty folder, Windows.old tree) + the parent removing its own result file",
          dels.count("[System.IO.File]::Delete(") == 1 and dels.count("[System.IO.Directory]::Delete(") == 1 and dels.count("Remove-Item") == 2, dels)
    for fn, want in (("Remove-SafeFile", "[System.IO.File]::Delete("), ("Remove-SafeEmptyDir", "[System.IO.Directory]::Delete("),
                     ("Remove-SafeTree", "Remove-Item")):
        m = re.search(r"function " + fn + r"\b.*?\n\}", body, re.S)
        check(f"{fn} holds its delete", m is not None and want in m.group(0))
    m = re.search(r"function Remove-SafeFile\b.*?\n\}", body, re.S)
    check("Remove-SafeFile checks the allow-list (Test-Deletable) before anything is deleted",
          m and m.group(0).index("Test-Deletable") < m.group(0).index("[System.IO.File]::Delete("))
    m = re.search(r"function Remove-SafeTree\b.*?\n\}", body, re.S)
    check("Remove-SafeTree only ever removes a folder called Windows.old that was registered", m and "Windows.old" in m.group(0)
          and "$script:TreeRoot" in m.group(0))
    check("no Stop-Process / taskkill / Kill (NinjaTrader and the bot are never closed)", not re.search(r"(?i)\b(Stop-Process|taskkill|\.Kill\()", body))
    check("nothing is downloaded or uploaded by the cleaner itself", not re.search(r"(?i)(Invoke-WebRequest|Invoke-RestMethod|Start-BitsTransfer|DownloadFile|\bcurl\b|\bwget\b)", body))
    check("no registry, service-startup or scheduled-task change (services only stop / start wuauserv and bits for the update cache)",
          not re.search(r"(?i)(Set-ItemProperty|New-ItemProperty|Set-Service|Register-ScheduledTask|schtasks|reg\.exe|powercfg)", body))
    m = re.search(r"\$ProtectName = @\((.*?)\)\n", body, re.S)
    prot = m.group(1) if m else ""
    for must in (r"^\.env", "^live_state", "^accounts", "journal", r"^memory\.db", r"^alerts\.json", "^autostart"):
        check(f"never-touch name list has {must}", must in prot, prot[:300])
    for must in ("nt_bars", "workspaces", "templates", "le_feed", "incoming", "outgoing"):
        check(f"never-touch folder list has {must}", re.search(r"\$ProtectDirAbs = @\([^)]*'" + must + "'", body) is not None)
    check("the Administrator test is inside try (it throws off Windows)", re.search(r"try\s*\{\s*\$isAdmin\s*=\s*\[bool\]" + re.escape(ADMIN_EXPR), code) is not None)
    # the bot / NinjaTrader running skip is wired to the two categories that touch them
    check("NinjaTrader and bot categories are gated 'trading' (skipped while either runs)",
          len(re.findall(r"New-Cat '(nt|bot)' [^\n]*'user' 'trading'", body)) == 2)
    check("Windows.old is skipped while the bot or NinjaTrader runs", body.count("$Busy") >= 6 and "skipped while the bot or NinjaTrader is running" in body)
    ba = rb(os.path.join(ROOT, "scripts", "clean_pc.ps1")).decode("utf-8", "replace")
    check("CLEAN_PC reaches it: clean_pc.ps1 -Storage hands over, the PC_KIT gets CLEAN_STORAGE.bat + clean_storage.ps1, the end hints at it",
          re.search(r"\[switch\]\$Storage", ba) and "clean_storage.ps1" in ba and "CLEAN_STORAGE.bat" in ba and ba.count("clean_storage.ps1") >= 3)


# ============================================================================================== the health line (engine/pc_health)
def health():
    sys.path.insert(0, ROOT)
    from engine import pc_health as H, live_publish as LP
    lv = lambda ls, k: next((x["level"] for x in ls if x["key"] == k), None)
    tx = lambda ls, k: next((x["text"] for x in ls if x["key"] == k), "")
    f = {"disk_free_gb": 40, "storage": {"free_gb": 40.0, "bot_gb": 3.1, "nt_gb": 9.8}}
    ls = H.lines(f)
    check("health: storage line is green with plenty free and says the sizes", lv(ls, "storage") == "green" and "bot 3.1 GB" in tx(ls, "storage")
          and "NinjaTrader 9.8 GB" in tx(ls, "storage") and "CLEAN_STORAGE" not in tx(ls, "storage"), ls)
    ls = H.lines({"disk_free_gb": 12, "storage": {"free_gb": 12.0, "bot_gb": 3.1, "nt_gb": None}})
    check("health: 12 GB free = amber with 'Run CLEAN_STORAGE.bat' as the fix", lv(ls, "storage") == "amber" and "Run CLEAN_STORAGE.bat" in tx(ls, "storage"), ls)
    ls = H.lines({"disk_free_gb": 1.2, "storage": {"free_gb": 1.2}})
    check("health: 1.2 GB free = red", lv(ls, "storage") == "red" and "Run CLEAN_STORAGE.bat" in tx(ls, "storage"), ls)
    check("health: no storage facts = no storage line (the old 8-line block is unchanged)",
          lv(H.lines({"disk_free_gb": 40}), "storage") is None and lv(H.lines({"disk_free_gb": 40}), "disk") == "green")
    b = {"t": 1, "level": "red", "lines": [{"key": "disk", "label": "Disk space", "level": "red", "text": "1.2 GB free"},
                                            {"key": "storage", "label": "Storage", "level": "red", "text": "1.2 GB free"}]}
    st = {}
    if os.environ.get("LE_PC_HEALTH_PUSH") != "0":
        n = H.red_notices(b, b, st, time.time())
        check("health: disk and storage both red = ONE push (the storage one is not sent twice)", len(n) == 1 and ":disk:" in n[0]["key"], n)
    # the sampler: one size scan, cached; sizes of a small tree; capped, never raises
    d = tempfile.mkdtemp(prefix="le_t_st_")
    try:
        os.makedirs(os.path.join(d, "bot", "data"))
        with open(os.path.join(d, "bot", "data", "x.bin"), "wb") as fh:
            fh.write(b"x" * 3_000_000)
        gb, capped = H.dir_gb(os.path.join(d, "bot"))
        check("health: dir_gb sums a tree and is not capped for a small one", abs(gb - 0.003) < 0.0005 and capped is False, (gb, capped))
        check("health: dir_gb of a missing folder is None", H.dir_gb(os.path.join(d, "nope"))[0] is None)
        s = H.Sampler(None, ps=None, root=os.path.join(d, "bot"), is_windows=False, t0=time.time() - 10_000)
        f1 = s.facts(time.time())
        check("health: Sampler.facts carries storage {free_gb, bot_gb, nt_gb} after the warm-up",
              isinstance(f1.get("storage"), dict) and f1["storage"].get("bot_gb") is not None and "nt_gb" in f1["storage"] and f1["storage"]["free_gb"] > 0, f1.get("storage"))
        s2 = H.Sampler(None, ps=None, root=os.path.join(d, "bot"), is_windows=False, t0=time.time())
        f2 = s2.facts(time.time())
        check("health: right after a start only the free space is read (no folder walk during the warm-up)",
              isinstance(f2.get("storage"), dict) and f2["storage"].get("bot_gb") is None and f2["storage"].get("free_gb") > 0, f2.get("storage"))
        blk = s.block(time.time())
        check("health: the block carries `storage` and the storage line", isinstance(blk.get("storage"), dict) and any(x["key"] == "storage" for x in blk["lines"]), blk)
        hb = {"t": blk["t"], "level": blk["level"], "lines": blk["lines"], "skipped": blk["skipped"], "storage": blk["storage"]}
        summ = LP.pc_health_summary(hb, blk["t"])
        keys = [x["key"] for x in (summ or {}).get("lines", [])]
        check("phone summary (Jarvis): Storage replaces the plain Disk line, 8 lines at most, label 'Storage'",
              summ and "storage" in keys and "disk" not in keys and len(keys) <= 8
              and next(x["label"] for x in summ["lines"] if x["key"] == "storage") == "Storage", summ)
        old = LP.pc_health_summary({"t": 1, "lines": [{"key": "disk", "level": "green", "text": "40 GB free"}]}, 5)
        check("phone summary: without a storage line the Disk line stays", old and [x["key"] for x in old["lines"]] == ["disk"], old)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ============================================================================================== pwsh
def find_pwsh():
    p = os.environ.get("LE_PWSH") or shutil.which("pwsh") or ("/usr/local/bin/pwsh" if os.path.exists("/usr/local/bin/pwsh") else None)
    return p if p and os.path.exists(p) else None


def lint(pwsh):
    r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-File", os.path.join(HARN, "lint51.ps1"), PS1], capture_output=True, text=True, timeout=120)
    found = [ln for ln in r.stdout.splitlines() if ln.strip()]
    check("clean_storage.ps1: 5.1 lint (parser tokens + AST): no PowerShell-7-only syntax, cmdlet parameters or encodings",
          r.returncode == 0 and not found, found or r.stderr)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class World:
    """A fake Windows PC in a temp dir. kind: bot present (default) or not (a Surface after the move)."""

    def __init__(self, bot: bool = True):
        self.dir = tempfile.mkdtemp(prefix="le_cs_")
        d = self.dir
        self.old, self.keep = [], []                        # files that must go / must stay (absolute paths)
        self.home = os.path.join(d, "home")
        self.bot = os.path.join(self.home, "nq-liquidity-engine")
        self.temp = os.path.join(d, "Temp")
        self.la = os.path.join(d, "LocalAppData")
        self.ap = os.path.join(d, "AppData")
        self.pd = os.path.join(d, "ProgramData")
        self.win = os.path.join(d, "Windows")
        self.nt = os.path.join(d, "OneDrive", "Documents", "NinjaTrader 8")
        self.winold = os.path.join(d, "Windows.old")
        self.has_bot = bot
        self.groups = {"temp": [], "browser": [], "thumbs": [], "dumps": [], "dev": [], "nt": [], "bot": [], "win": [], "winold": [], "decoy": []}
        for p in (self.home, self.temp, self.la, self.ap, self.pd, self.win):
            os.makedirs(p, exist_ok=True)
        os.makedirs(os.path.join(d, "OneDrive"), exist_ok=True)
        if bot:
            os.makedirs(os.path.join(self.bot, "scripts"))
            os.makedirs(os.path.join(self.bot, "engine"))
            open(os.path.join(self.bot, "server.py"), "w").write("#\n")
            open(os.path.join(self.bot, "engine", "ninjatrader.py"), "w").write("#\n")
            shutil.copy(PS1, os.path.join(self.bot, "scripts", "clean_storage.ps1"))
            self.script = os.path.join(self.bot, "scripts", "clean_storage.ps1")
        else:
            kit = os.path.join(d, "PC_KIT")
            os.makedirs(os.path.join(kit, "scripts"))
            shutil.copy(PS1, os.path.join(kit, "scripts", "clean_storage.ps1"))
            self.script = os.path.join(kit, "scripts", "clean_storage.ps1")
        self._build()

    def f(self, group, rel_root, rel, age_days, size=2048, must_go=True):
        p = os.path.join(rel_root, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(b"x" * size)
        t = time.time() - age_days * DAY
        os.utime(p, (t, t))
        (self.old if must_go else self.keep).append(p)
        self.groups.setdefault(group, []).append((p, must_go))
        return p

    def _build(self):
        T, L, A, P, W, N, B = self.temp, self.la, self.ap, self.pd, self.win, self.nt, self.bot
        # --- your account
        self.f("temp", T, "old.tmp", 5)
        self.f("temp", T, "sub/old2.tmp", 5)
        self.f("temp", T, "new.tmp", 0.01, must_go=False)                    # a fresh temp file stays
        self.two_day = os.path.join(T, "two_days.tmp")                      # goes in a normal run (1-day rule), stays while busy (3 days)
        open(self.two_day, "w").write("x" * 500)
        os.utime(self.two_day, (time.time() - 2 * DAY, time.time() - 2 * DAY))
        self.f("temp", T, "newsub/fresh.tmp", 0.01, must_go=False)
        os.makedirs(os.path.join(T, "emptyold"))
        t = time.time() - 5 * DAY
        os.utime(os.path.join(T, "emptyold"), (t, t))
        self.empty_old_dir = os.path.join(T, "emptyold")
        ed = os.path.join(L, "Microsoft", "Edge", "User Data")
        self.f("browser", ed, "Default/Cache/Cache_Data/f_000001", 3, 300_000)
        self.f("browser", ed, "Default/Code Cache/js/a", 3)
        self.f("browser", ed, "Default/GPUCache/data_0", 3)
        self.f("browser", ed, "ShaderCache/x", 3)
        self.f("browser", ed, "Default/Cookies", 400, must_go=False)
        self.f("browser", ed, "Default/Login Data", 400, must_go=False)
        self.f("browser", ed, "Default/History", 400, must_go=False)
        self.f("browser", ed, "Default/Network/Cookies", 400, must_go=False)
        self.f("browser", ed, "Default/Local Storage/leveldb/000003.log", 400, must_go=False)
        self.f("browser", os.path.join(L, "Google", "Chrome", "User Data"), "Profile 1/Cache/Cache_Data/c1", 3, 200_000)
        self.f("browser", os.path.join(L, "Google", "Chrome", "User Data"), "Profile 1/Login Data", 400, must_go=False)
        ff = os.path.join(L, "Mozilla", "Firefox", "Profiles", "abc.default")
        self.f("browser", ff, "cache2/entries/e1", 3, 100_000)
        self.f("browser", ff, "logins.json", 400, must_go=False)
        self.f("browser", ff, "key4.db", 400, must_go=False)
        ex = os.path.join(L, "Microsoft", "Windows", "Explorer")
        self.f("thumbs", ex, "thumbcache_96.db", 20, 90_000)
        self.f("thumbs", ex, "iconcache_32.db", 20)
        self.f("thumbs", ex, "settings.dat", 20, must_go=False)
        self.f("thumbs", L, "IconCache.db", 20)
        self.f("dumps", L, "CrashDumps/app.exe.123.dmp", 9, 50_000)
        self.f("dumps", L, "Microsoft/Windows/WER/ReportArchive/Report1/Report.wer", 9)
        self.f("dev", L, "npm-cache/_cacache/index-v5/aa", 30, 80_000)
        self.f("dev", A, "npm-cache/_logs/x.log", 30)
        self.f("dev", L, "pip/Cache/http/a/b", 30, 70_000)
        self.f("dev", L, "pip/wheelhouse-keep-me.whl", 30, must_go=False)         # not the pip cache
        # --- NinjaTrader 8 (inside OneDrive, as on the owner's PCs)
        self.f("nt", N, "log/log.20260101.00001.txt", 40, 5000)
        self.f("nt", N, "log/log.20261104.00001.txt", 0.1, must_go=False)
        self.f("nt", N, "trace/trace.20260101.00001.txt", 40, 5000)
        self.f("nt", N, "cache/chartcache.bin", 30, 40_000)
        self.f("nt", N, "db/cache/dc.bin", 30, 40_000)
        for rel in ("workspaces/Main.xml", "workspaces/_Workspaces.xml", "templates/Chart/le.xml", "bin/Custom/Indicators/LE_BarFeed.cs",
                    "db/tick/MNQ 12-26/20261103.ncd", "db/minute/MNQ 12-26/20261103.ncd", "db/day/MNQ 12-26/x.ncd", "db/replay/r.ncd",
                    "le_feed/MNQ_1m.csv", "le_feed/accounts.csv", "incoming/oif1.txt", "outgoing/ATI_Sim101_position.txt",
                    "backup/NinjaTrader 8 backup.zip"):
            self.f("nt", N, rel, 400, must_go=False)
        # --- decoys: old files of the owner that no category may ever touch (also under a hostile TEMP)
        self.f("decoy", self.home, "Documents/precious.docx", 400, must_go=False)
        self.f("decoy", self.home, "Desktop/notes.txt", 400, must_go=False)
        self.f("decoy", self.home, "Downloads/statement.pdf", 400, must_go=False)          # job 2026-11-04: a person's Downloads, keys and sign-ins
        self.f("decoy", self.home, "Downloads/setup.exe", 400, must_go=False)
        self.f("decoy", self.home, ".ssh/id_ed25519", 400, must_go=False)
        self.f("decoy", self.home, "Documents/keys/wallet.key", 400, must_go=False)
        self.f("decoy", self.temp, "server.pem", 400, must_go=False)                      # a key file lying in TEMP is never deleted by name
        self.f("decoy", self.dir, "Users/owner/Pictures/photo.jpg", 400, must_go=False)
        self.f("decoy", os.path.join(self.dir, "OneDrive"), "Documents/taxes.xlsx", 400, must_go=False)
        self.f("decoy", os.path.join(self.dir, "OneDrive", "Documents"), "Other/keep.txt", 400, must_go=False)
        self.f("decoy", N, "mynotes.txt", 400, must_go=False)
        self.f("decoy", N, "Other/old.cfg", 400, must_go=False)
        if self.has_bot:
            self.f("decoy", B, "docs/readme_old.md", 400, must_go=False)
            self.f("decoy", B, "notes_for_owner.txt", 400, must_go=False)
        # --- the bot folder
        if self.has_bot:
            self.f("bot", B, "logs/server.log", 30, 9000)
            self.f("bot", B, "logs/old_run.out", 30)
            self.f("bot", B, "logs/server.log.1", 30)
            self.f("bot", B, "logs/server-now.log", 0.2, must_go=False)
            for rel in ("logs/supervisor.pid", "logs/supervisor.stop", "logs/pc_watch.json", "logs/pc_health.json", "logs/selftest.json",
                        "logs/nt_workspaces-20260101/Main.xml", "logs/lit_journal-old.jsonl", "logs/accounts_note.txt"):
                self.f("bot", B, rel, 60, must_go=False)
            self.f("bot", B, "data/ninjatrader_state.json.corrupt-1760000000", 30, 3000)
            self.f("bot", B, "data/tv.json.corrupt-12", 30)
            for rel in ("data/live_state.json", "data/live_state.json.corrupt-5", "data/ninjatrader_state.json", "data/guards_state.json",
                        "data/accounts.json", "data/accounts_state.json.corrupt-7", "data/memory.db", "data/alerts.json", "data/tv.json",
                        "data/tv_device.json", "data/autostart.json", "data/lit_journal.jsonl", "data/lit_learning.json",
                        "data/nt_bars/MNQ_2026-10.csv", "data/nt_bars/old/x.csv", "data/brain/2026-10-01.jsonl", "data/NQ_5m.csv",
                        "data/trades_journal.csv", ".env.local.ps1", ".env", "live_model.json", "live_model_lit.json",
                        "engine/foo.py", "engine/live.py", "server.py", "scripts/run_bot.ps1", "ninjatrader/LE_BarFeed.cs",
                        "data/sub/anything.corrupt-9", "backups-note.txt"):
                if rel in ("server.py", "engine/ninjatrader.py"):
                    continue
                self.f("bot", B, rel, 200, must_go=False)
            self.f("bot", B, "engine/__pycache__/foo.cpython-312.pyc", 10, 6000)
            self.f("bot", B, "tools/__pycache__/x.cpython-312.pyc", 10)
            self.f("bot", B, "__pycache__/server.cpython-312.pyc", 10)
            self.f("bot", B, "engine/not_a_cache.pyc", 10, must_go=False)          # a .pyc outside __pycache__ is not ours
            self.f("bot", B, "reports/tmp/r1.txt", 30)
            self.f("bot", B, "reports/keep.txt", 30, must_go=False)
            for age, name in ((40, "le-backup-20260925-1635.zip"), (30, "le-backup-20261005-1635.zip"), (20, "le-backup-20261015-1635.zip"),
                              (10, "le-backup-20261025-1635.zip"), (1, "le-backup-20261103-1635.zip")):
                self.f("bot", B, f"backups/{name}", age, 20_000, must_go=age >= 30)       # newest 3 stay: 20, 10, 1 days
            self.f("bot", B, "backups/notes.txt", 90, must_go=False)
        # --- Windows
        self.f("win", W, "Temp/old.tmp", 5, 10_000)
        self.f("win", W, "Temp/sub/old2.tmp", 5)
        self.f("win", W, "Temp/new.tmp", 0.01, must_go=False)
        self.f("win", W, "SoftwareDistribution/Download/abc/update.cab", 3, 500_000)
        self.f("win", W, "SoftwareDistribution/DataStore/DataStore.edb", 3, must_go=False)       # the update database stays
        self.f("win", W, "ServiceProfiles/NetworkService/AppData/Local/Microsoft/Windows/DeliveryOptimization/Cache/c1", 3, 100_000)
        self.f("win", W, "Minidump/110426-1.dmp", 9, 60_000)
        self.f("win", W, "MEMORY.DMP", 9, 100_000)
        self.f("win", P, "Microsoft/Windows/WER/ReportArchive/Crash1/Report.wer", 9)
        self.f("win", W, "Logs/CBS/CBS.old.log", 30, 30_000)
        self.f("win", W, "Logs/CBS/CBS.log", 0.01, must_go=False)
        self.f("win", W, "Logs/DISM/dism.log", 30)
        self.f("win", W, "Logs/WindowsUpdate/WindowsUpdate.20260101.etl", 30)
        self.f("win", W, "System32/config/SYSTEM", 30, must_go=False)                           # never
        self.f("win", W, "explorer.exe", 30, must_go=False)
        # --- Windows.old (the whole tree goes, only when asked)
        for rel in ("Windows/System32/a.dll", "Users/old/Documents/x.docx", "Program Files/y/z.exe"):
            p = os.path.join(self.winold, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(b"x" * 200_000)
            self.groups["winold"].append((p, True))

    def all_files(self):
        out = {}
        for base, _, files in os.walk(self.dir):
            for n in files:
                p = os.path.join(base, n)
                if os.sep + ".cache" + os.sep in p or os.sep + "logs" + os.sep + "clean_storage-" in p or os.sep + "LiquidityEngine" + os.sep + "logs" in p:
                    continue
                st = os.stat(p)
                out[p] = (st.st_size, int(st.st_mtime))
        return out

    def env(self, strict=False, temp=None, elevated=False, answer="n", uac="yes", port=None, bin_bytes=None):
        e = dict(os.environ, TEMP=temp or self.temp, TMP=temp or self.temp, LOCALAPPDATA=self.la, APPDATA=self.ap, ProgramData=self.pd,
                 WINDIR=self.win, SystemDrive=self.dir, OneDrive=os.path.join(self.dir, "OneDrive"), NINJATRADER_FOLDER=self.nt,
                 USERPROFILE=self.home, HOME=self.home, COMPUTERNAME="TESTPC", PORT=str(port or free_port()),
                 LE_T_ELEVATED="1" if elevated else "0", LE_T_ANSWER=answer, LE_T_UAC=uac, LE_T_STUBS=STUBS, LE_T_STRICT="1" if strict else "0",
                 LE_T_PWSH=find_pwsh() or "pwsh", PSModulePath=os.environ.get("PSModulePath", ""))
        e.pop("LE_BOT_DIR", None)
        if bin_bytes is not None:
            e["LE_T_BIN_BYTES"] = str(bin_bytes)
        return e

    def run(self, pwsh, args, **kw):
        e = self.env(**kw)
        cmd = f". '{STUBS}'; & '{self.script}' {' '.join(args)}; [Console]::WriteLine('EXIT=' + $LASTEXITCODE)"
        r = subprocess.run([pwsh, "-NoProfile", "-NoLogo", "-NonInteractive", "-Command", cmd], capture_output=True, text=True,
                           timeout=240, env=e, cwd=self.dir)
        return r.stdout, r.stderr

    def log_text(self):
        for d in (os.path.join(self.bot, "logs"), os.path.join(self.la, "LiquidityEngine", "logs")):
            if os.path.isdir(d):
                for n in sorted(os.listdir(d)):
                    if n.startswith("clean_storage-"):
                        return open(os.path.join(d, n), encoding="utf-8-sig", errors="replace").read()
        return None

    def gone(self, group):
        return [p for p, go in self.groups[group] if go and os.path.exists(p)]

    def lost(self, group=None):
        groups = [group] if group else list(self.groups)
        return [p for g in groups for p, go in self.groups[g] if not go and not os.path.exists(p)]

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def digest(files: dict) -> str:
    return hashlib.sha256(repr(sorted(files.items())).encode()).hexdigest()


def start_fake_ninjatrader(workdir):
    """A REAL process whose name is NinjaTrader (a copy of `sleep`): Get-Process -Name NinjaTrader* sees it like on Windows."""
    exe = os.path.join(workdir, "NinjaTrader")
    shutil.copy("/bin/sleep", exe)
    os.chmod(exe, 0o755)
    p = subprocess.Popen([exe, "300"])
    time.sleep(0.4)
    return p


def start_fake_bot_port():
    """The bot server answering on its port (the script asks http://127.0.0.1:<PORT>)."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(5)
    return s, s.getsockname()[1]


def run_world(pwsh, strict: bool):
    """strict=True (StrictMode 2) repeats only the dry run, the full run and the NinjaTrader-running run: they cover every code path."""
    tag = " [StrictMode 2]" if strict else ""
    mon = {}

    def common(name, out, err, w=None):
        check(f"{name}: exit 0, no PowerShell error{tag}", "EXIT=0" in out and not err.strip(), (err or out)[-1200:])

    # ---------------------------------------------------------------- 1. -DryRun on the bot PC
    w = World()
    try:
        before = w.all_files()
        out, err = w.run(pwsh, ["-DryRun"], strict=strict)
        common("DryRun (bot PC, user account)", out, err)
        after = w.all_files()
        check(f"DryRun: not one file removed or touched (all {len(before)} files and times identical){tag}", digest(before) == digest(after),
              set(before) ^ set(after))
        check(f"DryRun: a plain table with sizes for every category, a TOTAL, the never-touched line{tag}",
              all(k in out for k in ("What can be freed", "Temporary files (your account)", "Browser caches (sign-ins stay)", "Thumbnail and icon caches",
                                     "NinjaTrader old logs and caches", "Bot old logs, backups and __pycache__", "Windows Update downloads",
                                     "Old Windows logs", "TOTAL", "Never touched")), out[-2500:])
        check(f"DryRun: says nothing was deleted, with a size{tag}", re.search(r"DRY RUN: nothing was deleted. It would free about [\d.,]+ (MB|GB|KB)", out), out[-800:])
        check(f"DryRun: no question asked, no Windows (UAC) request{tag}", "HARNESS-UAC" not in out and "Type Y" not in out)
        lg = w.log_text()
        check(f"DryRun: a log file exists in the bot's logs\\ folder with the table{tag}", lg and "What can be freed" in lg and "TOTAL" in lg, lg)
        mb = re.search(r"Temporary files \(your account\)\s+([\d.,]+) (KB|MB|GB)", out)
        check(f"DryRun: the temp row is the two old temp files (about 4 KB), not the fresh ones{tag}", mb and mb.group(2) == "KB" and 3 <= float(mb.group(1).replace(",", "")) <= 5, out[-2200:])
    finally:
        w.cleanup()

    # ---------------------------------------------------------------- 2. a full run, nothing running, UAC allowed (the child really runs)
    w = World()
    try:
        out, err = w.run(pwsh, ["-Yes"], strict=strict)
        common("full run (nothing running, answers N to the Recycle Bin and Windows.old)", out, err)
        for g in ("temp", "browser", "thumbs", "dumps", "dev", "nt", "bot", "win"):
            left = w.gone(g)
            check(f"full run: every old '{g}' file is gone{tag}", not left, [os.path.relpath(p, w.dir) for p in left])
        lost = w.lost()
        check(f"full run: NOT ONE protected / fresh file was removed ({sum(1 for g in w.groups.values() for _, go in g if not go)} checked){tag}",
              not lost, [os.path.relpath(p, w.dir) for p in lost])
        check(f"full run: a 2-day-old temp file is gone (1-day rule){tag}", not os.path.exists(w.two_day))
        check(f"full run: the empty old temp folder is gone, the fresh temp folder stays{tag}",
              not os.path.exists(w.empty_old_dir) and os.path.isdir(os.path.join(w.temp, "newsub")))
        check(f"full run: the newest 3 backups stay (20, 10, 1 days), the 40- and 30-day ones are gone{tag}",
              all(os.path.exists(os.path.join(w.bot, "backups", n)) for n in ("le-backup-20261015-1635.zip", "le-backup-20261025-1635.zip", "le-backup-20261103-1635.zip"))
              and not os.path.exists(os.path.join(w.bot, "backups", "le-backup-20260925-1635.zip")))
        check(f"full run: Windows.old is still there (the question was N){tag}", all(os.path.exists(p) for p, _ in w.groups["winold"]))
        check(f"full run: asked Windows for Administrator once, the elevated part ran and its sizes came back{tag}",
              out.count("HARNESS-UAC") == 1 and "CHILD| " in out and "WINDOWS PART (Administrator)" in out, out[-2500:])
        check(f"full run: the update service was stopped and started again around the download cache{tag}",
              out.index("HARNESS-SVC stop wuauserv") < out.index("HARNESS-SVC start wuauserv"), out[-3000:])
        check(f"full run: asks before the Recycle Bin / Windows.old and does neither on N{tag}", "HARNESS-BIN" not in out and "HARNESS-TAKEOWN" not in out)
        m = re.search(r"Freed ([\d.,]+) (KB|MB|GB), C: now ([\d.,]+ GB free|not readable)\.", out)
        check(f"full run: ends with 'Freed X, C: now Y GB free'{tag}", m, out[-1500:])
        if m:
            mult = {"KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}[m.group(2)]
            check(f"full run: the freed figure is at least the 1.5 MB of known junk (both parts added){tag}", float(m.group(1).replace(",", "")) * mult >= 1.5 * 1024 ** 2, m.group(0))
        lg = w.log_text()
        check(f"full run: the log lists removed files with their sizes, user and Windows part{tag}",
              lg and re.search(r"removed\s+[\d,]+\s+.*old\.tmp", lg) and "update.cab" in lg and "WINDOWS PART" in lg, (lg or "")[:1500])
        check(f"full run: nothing in the log or output says REFUSED (nothing off the list was even tried){tag}", "REFUSED" not in (lg or "") and "refused by the safety list" not in out)
        # a second run finds nothing more to do
        out2, err2 = w.run(pwsh, ["-DryRun"], strict=strict)
        check(f"second DryRun after cleaning: about nothing left (under 100 KB){tag}", re.search(r"TOTAL \(without the two below\)\s+(0|\d{1,2} KB)\b", out2), out2[-1500:])
    finally:
        w.cleanup()

    if strict:
        w = World()
        nt = start_fake_ninjatrader(w.dir)
        try:
            out, err = w.run(pwsh, ['-Yes', '-Extras'], strict=True)
            common('NinjaTrader RUNNING', out, err)
            check(f'NinjaTrader running: bot + NinjaTrader folders untouched, Windows.old kept{tag}', not [p for g in ('nt', 'bot') for p, _ in w.groups[g] if not os.path.exists(p)] and os.path.exists(w.winold), out[-800:])
        finally:
            nt.kill()
            nt.wait()
            w.cleanup()
        return

    # ---------------------------------------------------------------- 3. the extras: Recycle Bin + Windows.old
    w = World()
    try:
        out, err = w.run(pwsh, ["-Yes", "-Extras"], strict=strict, bin_bytes=5_000_000)
        common("run with -Extras (Recycle Bin 5 MB + Windows.old)", out, err)
        check(f"-Extras: Recycle Bin emptied, Windows.old taken over and removed in the Windows part{tag}",
              "HARNESS-BIN emptied" in out and "HARNESS-TAKEOWN" in out and not os.path.exists(w.winold), out[-2500:])
        check(f"-Extras: protected files still all there{tag}", not w.lost())
    finally:
        w.cleanup()

    # ---------------------------------------------------------------- 4. the questions: N stops everything
    w = World()
    try:
        before = w.all_files()
        out, err = w.run(pwsh, [], strict=strict, answer="n")
        common("main question answered N", out, err)
        check(f"main question N: 'Stopped: nothing was deleted', every file unchanged{tag}", "Stopped: nothing was deleted" in out and digest(before) == digest(w.all_files()))
        out, err = w.run(pwsh, [], strict=strict, answer="y", bin_bytes=1_000_000)
        common("main question answered Y (and Y to the extras)", out, err)
        check(f"main question Y: cleans, and Y to the extras empties the Recycle Bin and removes Windows.old{tag}",
              "HARNESS-BIN emptied" in out and not os.path.exists(w.winold) and not w.gone("temp") and not w.lost(), out[-1500:])
    finally:
        w.cleanup()

    # ---------------------------------------------------------------- 5. NinjaTrader running
    w = World()
    nt = start_fake_ninjatrader(w.dir)
    try:
        out, err = w.run(pwsh, ["-Yes", "-Extras"], strict=strict)
        common("NinjaTrader RUNNING (a real process named NinjaTrader)", out, err)
        check(f"NinjaTrader running: it says so and what is skipped{tag}", "NinjaTrader RUNNING" in out and "The bot or NinjaTrader is running" in out
              and "skipped (bot or NinjaTrader running)" in out, out[:2500])
        untouched = [p for g in ("nt", "bot") for p, _ in w.groups[g] if not os.path.exists(p)]
        check(f"NinjaTrader running: NOT ONE file of the NinjaTrader folder or the bot folder was removed (old logs included){tag}", not untouched,
              [os.path.relpath(p, w.dir) for p in untouched][:8])
        check(f"NinjaTrader running: Windows.old kept even with -Extras{tag}", all(os.path.exists(p) for p, _ in w.groups["winold"]) and "HARNESS-TAKEOWN" not in out)
        check(f"NinjaTrader running: temp files, browser caches and Windows junk ARE cleaned{tag}",
              not w.gone("temp") and not w.gone("browser") and not w.gone("thumbs") and not w.gone("dev") and not w.gone("win"),
              [os.path.relpath(p, w.dir) for g in ("temp", "browser", "win") for p in w.gone(g)][:8])
        check(f"NinjaTrader running: protected browser / temp / Windows files stay{tag}", not w.lost("browser") and not w.lost("temp") and not w.lost("win"))
        lg = w.log_text() or ""
        rem = [ln for ln in lg.splitlines() if ln.strip().startswith("removed")]
        check(f"NinjaTrader running: the log lists removed files, none from the NinjaTrader or bot folder{tag}",
              rem and not [ln for ln in rem if "NinjaTrader 8" in ln or "nq-liquidity-engine" in ln], rem[:3])
        check(f"NinjaTrader running: a 2-day-old temp file is kept (3-day rule while busy), the 5-day ones went{tag}", os.path.exists(w.two_day))
    finally:
        nt.kill()
        nt.wait()
        w.cleanup()

    # ---------------------------------------------------------------- 6. the bot running (its port answers)
    w = World()
    sock, port = start_fake_bot_port()
    try:
        out, err = w.run(pwsh, ["-Yes"], strict=strict, port=port)
        common("bot RUNNING (its port answers)", out, err)
        check(f"bot running: says 'bot RUNNING' and skips the bot + NinjaTrader folders{tag}", "bot RUNNING" in out and "skipped (bot or NinjaTrader running)" in out, out[:2000])
        untouched = [p for g in ("nt", "bot") for p, _ in w.groups[g] if not os.path.exists(p)]
        check(f"bot running: not one file of the bot or NinjaTrader folder removed{tag}", not untouched, [os.path.relpath(p, w.dir) for p in untouched][:8])
        check(f"bot running: Windows and caches still cleaned{tag}", not w.gone("win") and not w.gone("browser") and not w.gone("temp"))
    finally:
        sock.close()
        w.cleanup()

    # ---------------------------------------------------------------- 7. hostile TEMP: the allow-list cannot be widened
    for label, tmp_rel, expect_forbidden in (
            ("the user profile", "home", True), ("the bot folder", "home/nq-liquidity-engine", True),
            ("the Downloads folder", "home/Downloads", True), ("the Desktop folder", "home/Desktop", True), ("the .ssh key folder", "home/.ssh", True),
            ("a folder inside Documents", "home/Documents/keys", True), ("a folder inside OneDrive\\Documents", "OneDrive/Documents/Other", True),
            ("the NinjaTrader folder", "OneDrive/Documents/NinjaTrader 8", True), ("the system drive root", "", True),
            ("the bot's data folder", "home/nq-liquidity-engine/data", False), ("the bot's data\\nt_bars", "home/nq-liquidity-engine/data/nt_bars", False),
            ("NinjaTrader's workspaces", "OneDrive/Documents/NinjaTrader 8/workspaces", False),
            ("NinjaTrader's db", "OneDrive/Documents/NinjaTrader 8/db", False),
            ("NinjaTrader's db\\tick", "OneDrive/Documents/NinjaTrader 8/db/tick", False),
            ("NinjaTrader's incoming (orders)", "OneDrive/Documents/NinjaTrader 8/incoming", False),
            ("the bot's logs folder with its pid files", "home/nq-liquidity-engine/logs", False)):
        w = World()
        try:
            hostile = os.path.join(w.dir, *tmp_rel.split("/")) if tmp_rel else w.dir
            decoys = [p for p, _ in w.groups["decoy"] if p.startswith(os.path.join(os.path.normpath(hostile), ""))]
            protected = [p for g in w.groups.values() for p, go in g if not go]
            out, err = w.run(pwsh, ["-Yes"], strict=strict, temp=hostile)
            common(f"hostile TEMP = {label}", out, err)
            gone_prot = [os.path.relpath(p, w.dir) for p in protected if not os.path.exists(p)]
            check(f"hostile TEMP = {label}: not one protected file (state, workspaces, db, orders, .env, accounts, nt_bars ...) was deleted{tag}",
                  not gone_prot, gone_prot[:8])
            if expect_forbidden:
                check(f"hostile TEMP = {label}: refused as a root, the owner's old files in it (decoys) are all still there ({len(decoys)}){tag}",
                      decoys and all(os.path.exists(p) for p in decoys), decoys)
        finally:
            w.cleanup()

    # ---------------------------------------------------------------- 8. Surface without a bot folder
    w = World(bot=False)
    try:
        out, err = w.run(pwsh, ["-Yes"], strict=strict)
        common("Surface without a bot folder", out, err)
        check(f"no bot folder: says so, cleans temp / browser / NinjaTrader old logs / Windows, protected files stay{tag}",
              "no bot folder on this PC" in out and not w.gone("temp") and not w.gone("browser") and not w.gone("nt") and not w.gone("win") and not w.lost(), out[:1500])
        lg = w.log_text()
        check(f"no bot folder: the log is in %LOCALAPPDATA%\\LiquidityEngine\\logs{tag}", lg and "removed" in lg, os.listdir(w.la))
    finally:
        w.cleanup()

    # ---------------------------------------------------------------- 9. UAC declined
    w = World()
    try:
        out, err = w.run(pwsh, ["-Yes", "-Extras"], strict=strict, uac="no", bin_bytes=1000)
        common("UAC declined", out, err)
        check(f"UAC declined: the user part is done, Windows junk and Windows.old stay, it says why{tag}",
              not w.gone("temp") and not w.gone("browser") and w.gone("win") and all(os.path.exists(p) for p, _ in w.groups["winold"])
              and "Administrator was declined" in out and not w.lost(), out[-1500:])
    finally:
        w.cleanup()

    # ---------------------------------------------------------------- 10. the elevated part by itself (what the UAC window runs)
    w = World()
    try:
        out, err = w.run(pwsh, ["-SystemPart", "-DryRun", "-WithWinOld"], strict=strict, elevated=True)
        common("-SystemPart -DryRun (Administrator)", out, err)
        check(f"-SystemPart -DryRun: lists the Windows categories, deletes nothing{tag}", "Windows Update downloads" in out and not w.lost() and not w.gone("win") == [] and "HARNESS-" not in out.replace("HARNESS-SVC", ""), out[-1500:])
        out, err = w.run(pwsh, ["-SystemPart", "-WithWinOld"], strict=strict, elevated=True)
        common("-SystemPart (Administrator)", out, err)
        check(f"-SystemPart: Windows junk gone, Windows.old gone, the user's temp / NinjaTrader / bot untouched, protected Windows files stay{tag}",
              not w.gone("win") and not os.path.exists(w.winold) and w.gone("temp") and w.gone("nt") and w.gone("bot") and not w.lost(), out[-1500:])
    finally:
        w.cleanup()


def main() -> int:
    static()
    health()
    pwsh = find_pwsh()
    if pwsh:
        lint(pwsh)
        run_world(pwsh, strict=False)
        run_world(pwsh, strict=True)
    else:
        print("[SKIP] pwsh checks: pwsh not found (set LE_PWSH=<path> or install PowerShell 7)")
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


def test_clean_storage():                  # pytest entry
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
