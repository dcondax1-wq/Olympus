"""UPDATE_FROM_ZIP.bat / UNDO_UPDATE.bat / tools/update_from_zip.py: updating the bot folder from a code zip, without GitHub (2026-11-11).

Like tests/test_win_scripts.py: the .bat files are linted statically (CRLF, ASCII, labels, the run-from-a-copy rule), and the real
work (tools/update_from_zip.py, plain Python, the same file the PC runs) really runs against FAKE bot folders and FAKE zips in a
temp folder, with a fake clock (--now) and a fake "bot is running" (a socket on a free port). The first-run bootstrap line of the
.bat (python -c "...") is cut out of the .bat and really run too.

  1. static   the two .bat files, the tool is stdlib only, no network, no process killing, never starts the bot
  2. units    New York time and market hours without a tz database, the .gitignore matcher, safe paths, same-content, the .sha256.txt line
  3. flows    dry run, market open, bot running, bad SHA-256, the update itself (local-only files, live_model*.json kept, six lines,
              the backup), run twice, undo, undo after an edit, a failed write rolls back, wrong folder, no zip, the zip found in Downloads

Nothing touches the real repo, the real bot or the network.   python -X utf8 -m tests.test_update_from_zip
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import update_from_zip as U  # noqa: E402
from tests.test_win_scripts import lint_bat  # noqa: E402

TOOL = os.path.join(ROOT, "tools", "update_from_zip.py")
RES = []
SAT = 1794672000.0          # Sat 2026-11-14 16:00 UTC = 11:00 ET: market closed
WED = 1794412800.0          # Wed 2026-11-11 16:00 UTC = 11:00 ET: market open


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:1200]})" if detail and not cond else ""), flush=True)
    return bool(cond)


def rb(p):
    with open(p, "rb") as fh:
        return fh.read()


def wr(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def tree(folder, skip=("backups",)):
    """{relative path: sha256} of every file (the backups folder left out)."""
    out = {}
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not (root == folder and d in skip)]
        for f in files:
            p = os.path.join(root, f)
            out[os.path.relpath(p, folder).replace(os.sep, "/")] = hashlib.sha256(rb(p)).hexdigest()
    return out


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# ------------------------------------------------------------------------------------------------ the fake world
GITIGNORE = rb(os.path.join(ROOT, ".gitignore")).decode("utf-8")
LOCAL_ONLY = {            # the owner's local-only files: every one must come through an update byte for byte
    "data/alerts.json": '{"telegram_token": "LOCAL-SECRET-DO-NOT-TOUCH"}',
    "data/tv.json": '{"tv": "local"}', "data/tv_device.json": '{"device": "local"}', "data/autostart.json": '{"autostart": true}',
    "data/live_state.json": '{"position": null, "day": "2026-11-10"}', "data/memory.db": b"SQLite format 3\0local-memory",
    ".env": "LE_PHRASE=local", ".env.local": "X=1", "data/nt_bars/2026-11-10.csv": "t,o,h,l,c\n1,2,3,4,5\n", "logs/bot-20261110.log": "local log\n",
    "data/lite.json": '{"lite": true}', "data/account_b.json": '{"account": "LOCAL-B"}', "data/eval_anchor.json": '{"balance": 49313.54}',
}
MODEL_SAME_LOCAL = '{\r\n  "strategy": "lit",\r\n  "no_yahoo": true,\r\n  "lit": {"be_r": 1.0}\r\n}\r\n'      # the same values as the zip, CRLF + other spacing
MODEL_SAME_ZIP = '{"strategy": "lit", "no_yahoo": true, "lit": {"be_r": 1.0}}\n'
MODEL_LIT_LOCAL = '{"lit_sizing": {"mode": "two_week", "room_f": 0.6}}\n'                                 # the owner changed room_f
MODEL_LIT_ZIP = '{"lit_sizing": {"mode": "two_week", "room_f": 0.8}}\n'


def make_bot(base):
    bot = os.path.join(base, "bot")
    files = {
        "engine/lit.py": "VERSION = 'old'\n", "server.py": "print('server')\n", "engine/live.py": "LIVE = 1\r\n", "tools/old_tool.py": "# only in the old folder\n",
        "README.md": "line one\r\nline two\r\n", "START_BOT.bat": "@echo off\r\necho start\r\n", "live_model.json": MODEL_SAME_LOCAL, "live_model_lit.json": MODEL_LIT_LOCAL,
        "live_model_engine.json": '{"engine": 1}\n', ".gitignore": GITIGNORE, "docs/NOTES.md": "old notes\n", "tools/blocker": "a FILE where the bad zip wants a folder\n",
        **LOCAL_ONLY,
    }
    for rel, data in files.items():
        wr(os.path.join(bot, rel.replace("/", os.sep)), data)
    return bot


ZIP_FILES = {
    "engine/lit.py": "VERSION = 'new'\n", "server.py": "print('server')\n", "engine/live.py": "LIVE = 1\n", "engine/new_mod.py": "NEW = True\n",
    "README.md": "line one\nline two\n", "START_BOT.bat": "@echo off\r\necho start v2\r\n", "UNDO_UPDATE.bat": "@echo off\r\n", "live_model.json": MODEL_SAME_ZIP,
    "live_model_lit.json": MODEL_LIT_ZIP, "live_model_engine.json": '{"engine": 1}\n', ".gitignore": GITIGNORE, "docs/NOTES.md": "new notes\n", "docs/deep/a/b/c.md": "deep\n",
    "tools/update_from_zip.py": rb(TOOL), "requirements.txt": "tzdata\n",
    # things a zip should never hold; the updater must not write any of them
    "data/alerts.json": '{"telegram_token": "FROM-THE-ZIP"}', "logs/evil.log": "zip log\n", "data/nt_bars/evil.csv": "x\n", ".env": "LE_PHRASE=zip", "data/memory.db": b"zip-db",
    "data/lite.json": '{"lite": false}', "data/live_state_atlas_v2.json": '{"zip": 1}', "backups/x.txt": "zip\n", ".git/config": "zip\n",
    "../evil_parent.txt": "escape\n", "/abs_evil.txt": "abs\n", "C:/drive_evil.txt": "drive\n", "docs/../../evil_dots.txt": "dots\n",
}


def make_zip(base, name="OLYMPUS_BACKUP_2026-11-11_abc1234.zip", files=None, sha="good", where=None):
    d = where or os.path.join(base, "dl")
    os.makedirs(d, exist_ok=True)
    zp = os.path.join(d, name)
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, data in (files or ZIP_FILES).items():
            z.writestr(rel, data)
    digest = hashlib.sha256(rb(zp)).hexdigest()
    stem = name[:-4]
    if sha == "good":            # exactly the line tools/make_backup.py writes
        wr(os.path.join(d, stem + ".sha256.txt"), f"{digest}  {name}  {os.path.getsize(zp) / 1048576:.1f} MB\n")
    elif sha == "bad":
        wr(os.path.join(d, stem + ".sha256.txt"), f"{'0' * 64}  {name}  0.1 MB\n")
    return zp


def run(args, home, port, now=SAT):
    env = {**os.environ, "HOME": home, "USERPROFILE": home, "PYTHONIOENCODING": "utf-8"}
    env.pop("PORT", None)
    r = subprocess.run([sys.executable, "-X", "utf8", TOOL, "--port", str(port), "--now", str(now), *args], capture_output=True, text=True, env=env, timeout=120)
    return r.returncode, r.stdout + r.stderr


def six_lines(out):
    return [ln for ln in out.splitlines() if re.match(r"^ [1-6]\. \S", ln)]


# ============================================================================================== 1. static
def test_static():
    upd, undo = rb(os.path.join(ROOT, "UPDATE_FROM_ZIP.bat")), rb(os.path.join(ROOT, "UNDO_UPDATE.bat"))
    for name, raw in (("UPDATE_FROM_ZIP.bat", upd), ("UNDO_UPDATE.bat", undo)):
        probs = lint_bat(name, raw)
        check(f"1. {name}: CRLF, ASCII, labels and paths exist, balanced parentheses", not probs, probs)
        txt = raw.decode("ascii")
        check(f"1. {name}: runs from a temp copy (the update / undo can rewrite or remove the running .bat)",
              re.search(r'(?im)^copy\s+/y\s+"%~f0"\s+"%TEMP%[^\r\n]*\r\ncall\s+"%TEMP%[^\r\n]*&\s*exit\s+/b', txt) and re.search(r'(?im)^if /i "%~1"=="--from-temp" goto :main', txt))
        code = "\r\n".join(ln for ln in txt.split("\r\n") if not ln.strip().lower().startswith(("rem", "echo")))
        check(f"1. {name}: never starts, stops or arms the bot, never calls git / powershell / NinjaTrader, ends with a pause",
              not re.search(r"(?i)start_bot|stop_bot|/api/live|\bgit\b|powershell|ninjatrader|taskkill|schtasks", code) and "pause" in code, re.findall(r"(?i)start_bot|stop_bot|/api/live|\bgit\b|powershell|taskkill", code))
    t = upd.decode("ascii")
    check("1. UPDATE_FROM_ZIP.bat: uses the folder's own updater, else takes it out of the zip (first run); asks before updating while the market is open (exit code 12); passes a dragged zip on",
          'if exist "%TOOL%" goto :run' in t and "tools/update_from_zip.py" in t and 'if not "%errorlevel%"=="12" goto :end' in t and "--allow-market-open" in t and "Type Y then Enter" in t and '"%~1"' in t and "--force" not in t)
    check("1. UNDO_UPDATE.bat: runs the updater with --undo from a temp copy of the tool (the undo may remove the tool itself)", "--undo" in undo.decode() and 'le_update_from_zip.py" --undo' in undo.decode())
    src = rb(TOOL).decode("utf-8")
    imports = set(re.findall(r"^(?:import|from)\s+([a-zA-Z_][\w.]*)", src, re.M)) - {"__future__"}
    std = {"argparse", "datetime", "fnmatch", "glob", "hashlib", "json", "os", "re", "shutil", "socket", "subprocess", "sys", "time", "zipfile"}
    check("1. the tool is stdlib only and does not import the bot (it also runs from %TEMP%, outside the repo)", imports <= std, imports - std)
    code = re.sub(r'""".*?"""', "", src, flags=re.S)
    check("1. the tool has no network client, never kills a process, never runs git, never deletes a folder outside its own backups, no zoneinfo",
          not re.search(r"urllib|http\.client|requests|os\.kill|taskkill|\[\"git\"|'git'|zoneinfo|extractall", code) and code.count("shutil.rmtree") == 1 and "prune_backups" in code)
    check("1. the only subprocess is pip for requirements.txt, and only with --pip", code.count("subprocess.run") == 1 and '"-m", "pip", "install"' in code and "a.pip" in code)
    check("1. the hard local-only list names what the owner listed (alerts, tv, tv_device, autostart, live_state, memory.db, .env*, nt_bars, logs)",
          all(x in U.HARD_LOCAL for x in ("data/alerts.json", "data/tv.json", "data/tv_device.json", "data/autostart.json", "data/live_state.json", "data/memory.db", ".env", ".env.*", "data/nt_bars/", "logs/")))
    check("1. live_model*.json is the keep-if-changed rule; a wrong SHA-256 has no force path", U.KEEP_IF_CHANGED == ("live_model*.json",) and "EXIT_BADZIP" in src and src.index("check_zip(zip_path)") < src.index("rc = guards(a, folder)"))
    for b in ("UPDATE_FROM_ZIP.bat", "UNDO_UPDATE.bat"):
        ga = subprocess.run(["git", "check-attr", "eol", "--", b], capture_output=True, text=True, cwd=ROOT).stdout
        check(f"1. {b}: .gitattributes keeps it CRLF", "eol: crlf" in ga, ga)


# ============================================================================================== 2. units
def test_units():
    et = lambda s: U.et_now(s).strftime("%a %Y-%m-%d %H:%M")  # noqa: E731
    check("2. New York time without a tz database: winter (UTC-5), summer (UTC-4), both change-over Sundays of 2026 and 2027",
          et(WED) == "Wed 2026-11-11 11:00" and et(1783958400.0) == "Mon 2026-07-13 12:00" and et(1772953199.0) == "Sun 2026-03-08 01:59" and et(1772953200.0) == "Sun 2026-03-08 03:00"
          and et(1793512799.0) == "Sun 2026-11-01 01:59" and et(1793512800.0) == "Sun 2026-11-01 01:00" and et(1805007600.0) == "Sun 2027-03-14 03:00",
          [et(x) for x in (WED, 1783958400.0, 1772953199.0, 1772953200.0, 1793512799.0, 1793512800.0, 1805007600.0)])
    try:
        from zoneinfo import ZoneInfo
        import datetime as dt
        ny = ZoneInfo("America/New_York")
        bad = [t for t in range(1767225600, 1767225600 + 2 * 366 * 86400, 5 * 3600 + 1800) if U.et_now(t) != dt.datetime.fromtimestamp(t, ny).replace(tzinfo=None)]
        check("2. the same New York time as the tz database for every 5.5 hours of 2026 and 2027", not bad, bad[:3])
    except Exception as e:
        check(f"2. tz database not available here ({e.__class__.__name__}): cross-check skipped", True)
    mo = U.market_open
    h = 3600
    check("2. market hours (CME index futures): open Wed 11:00 ET, closed Sat, closed Sun 17:59, open Sun 18:00, open Fri 16:59, closed Fri 17:00, closed Wed 17:30 (the daily break), open Wed 18:00",
          mo(WED) and not mo(SAT) and not mo(SAT + 24 * h + 7 * h - 60) and mo(SAT + 24 * h + 7 * h) and mo(WED + 2 * 24 * h + 6 * h - 60) and not mo(WED + 2 * 24 * h + 6 * h) and not mo(WED + 6.5 * h) and mo(WED + 7 * h),
          [mo(WED), mo(SAT), mo(SAT + 31 * h - 60), mo(SAT + 31 * h), mo(WED + 54 * h - 60), mo(WED + 54 * h), mo(WED + 6.5 * h), mo(WED + 7 * h)])
    pats = U.ignore_patterns(GITIGNORE)
    m = lambda rel: bool(U.matches(rel, pats))  # noqa: E731
    check("2. the repo's .gitignore is understood: local files match, tracked code does not",
          all(m(x) for x in ("data/alerts.json", "data/tv.json", "data/live_state.json", "data/memory.db", "data/memory.db-wal", ".env", ".env.local", "prod.env", "data/nt_bars/a/b.csv", "logs/x.log", "engine/__pycache__/a.pyc",
                             "backups/2026/x.json", "data/live_state_fleet7.json", "data/pc_publish/site/index.html", "PC_REPORT-1.txt", "data/brain/2026-11-10.jsonl", "data/x_pause.json"))
          and not any(m(x) for x in ("engine/lit.py", "live_model.json", "data/NQ_5m.csv", "docs/logs.md", "tools/env.py", "data/alerts.example.json", "research/lit/lit_final.json", "UPDATE_FROM_ZIP.bat", "data/nt_bars.md")),
          [x for x in ("engine/lit.py", "live_model.json", "data/NQ_5m.csv", "docs/logs.md", "tools/env.py", "data/nt_bars.md") if m(x)])
    hm = lambda rel: bool(U.matches(rel, U.HARD_LOCAL))  # noqa: E731
    check("2. the hard list: the owner's files and folders, in any letter case, and nothing of the code",
          all(hm(x) for x in ("data/alerts.json", "DATA/Alerts.json", "data/tv_device.json", "data/live_state.json", "data/live_state_acctc.json", "data/memory.db", "data/memory.db-shm", ".env", ".env.prod", "x/.env", "data/nt_bars/x.csv",
                              "logs/a/b.log", "backups/x", ".git/config", "data/account_b.json"))
          and not any(hm(x) for x in ("engine/lit.py", "live_model.json", "data/alerts_plus.md", "tools/logs.py", "docs/env.md", "data/NQ_5m.csv")))
    check("2. unsafe zip paths are refused: parent folders, absolute, drive letters, odd characters; normal ones pass",
          [U.safe_rel(x) for x in ("../a", "/a", "C:/a", "a/../b", "a//b", "a/./b", "dir/", "a:b", "a\\..\\b", "con?", "")] == [None] * 11 and U.safe_rel("engine/lit.py") == "engine/lit.py" and U.safe_rel("a\\b.txt") == "a/b.txt")
    check("2. the same file with Windows line ends counts as the same; a .bat, a binary or a real change does not",
          U.same_content("a.py", b"x\r\ny\r\n", b"x\ny\n") and not U.same_content("a.bat", b"x\r\n", b"x\n") and not U.same_content("a.bin", b"\0x\r\n", b"\0x\n") and not U.same_content("a.py", b"x\n", b"y\n"))
    check("2. live_model*.json is compared by VALUE (spacing and line ends do not count); only root-level live_model*.json is a model file",
          U.same_json(MODEL_SAME_LOCAL.encode(), MODEL_SAME_ZIP.encode()) and not U.same_json(MODEL_LIT_LOCAL.encode(), MODEL_LIT_ZIP.encode()) and not U.same_json(b"{", b"{")
          and U.is_model("live_model.json") and U.is_model("live_model_lit.json") and not U.is_model("research/live_model.json") and not U.is_model("second_model.json"))


# ============================================================================================== 3. flows
def test_flows():
    base = tempfile.mkdtemp(prefix="upd-zip-")
    home = os.path.join(base, "home")
    os.makedirs(home)
    port = free_port()
    try:
        bot = make_bot(base)
        zp = make_zip(base)
        before = tree(bot)

        # ---- dry run
        rc, out = run([zp, "--folder", bot, "--dry-run"], home, port)
        check("3. dry run: exit 0, six lines, 'would be: 3 updated, 5 new', nothing changed, no backup made",
              rc == 0 and len(six_lines(out)) == 6 and "would be: 3 updated, 5 new" in out and tree(bot) == before and not os.path.exists(os.path.join(bot, "backups")), out)

        # ---- market open
        rc, out = run([zp, "--folder", bot], home, port, now=WED)
        check("3. the market is open (Wed 11:00 ET): refused with exit 12 and the best time, nothing changed", rc == 12 and "futures market is open (Wed 11:00 ET)" in out and "17:00-18:00 ET" in out and tree(bot) == before, out)
        rc, out = run([zp, "--folder", bot, "--allow-market-open", "--dry-run"], home, port, now=WED)
        check("3. ...and with the owner's Y (--allow-market-open) it goes on", rc == 0 and "would be:" in out, out)

        # ---- bot running
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(5)
        try:
            rc, out = run([zp, "--folder", bot], home, port)
            check("3. the bot is running (its server answers on the port): refused with exit 11, 'STOP_BOT.bat first', nothing changed, also with --allow-market-open",
                  rc == 11 and "The bot is running" in out and "STOP_BOT.bat" in out and tree(bot) == before and run([zp, "--folder", bot, "--allow-market-open"], home, port)[0] == 11, out)
            rc, out = run([zp, "--folder", bot, "--force", "--dry-run"], home, port, now=WED)
            check("3. --force is the only way past a running bot and an open market", rc == 0 and "would be:" in out, out)
            rc, out = run(["--undo", "--folder", bot], home, port)
            check("3. undo with nothing saved says so (exit 2) and changes nothing", rc == 2 and "Nothing to undo" in out and tree(bot) == before, out)
        finally:
            srv.close()

        # ---- bad zips
        bad = make_zip(base, name="OLYMPUS_BACKUP_2026-11-11_bad0000.zip", sha="bad")
        rc, out = run([bad, "--folder", bot, "--force"], home, port)
        check("3. a zip whose SHA-256 does not match its .sha256.txt: refused with exit 3 even with --force, nothing changed", rc == 3 and "SHA-256 does NOT match" in out and tree(bot) == before, out)
        notzip = os.path.join(base, "dl", "OLYMPUS_BACKUP_2026-11-11_junk.zip")
        wr(notzip, b"this is not a zip")
        rc, out = run([notzip, "--folder", bot], home, port)
        check("3. a file that is not a zip: exit 3, nothing changed", rc == 3 and "does not open" in out and tree(bot) == before, out)
        other = make_zip(base, name="OLYMPUS_BACKUP_2026-11-11_other.zip", files={"README.md": "x", "foo/bar.py": "y"}, sha="none")
        rc, out = run([other, "--folder", bot], home, port)
        check("3. a zip of something else (no engine/lit.py in it): exit 3, nothing changed", rc == 3 and "not the bot's code zip" in out and tree(bot) == before, out)
        rc, out = run([zp, "--folder", os.path.join(base, "dl")], home, port)
        check("3. a folder that is not the bot folder: exit 2, nothing written there", rc == 2 and "is not the bot folder" in out, out)
        rc, out = run(["--folder", bot], home, port)
        check("3. no zip given and none in the folder / Downloads / Desktop: exit 2 with what to do", rc == 2 and "Download the code zip" in out and tree(bot) == before, out)

        # ---- the update
        rc, out = run([zp, "--folder", bot], home, port)
        after = tree(bot)
        lines = six_lines(out)
        check("3. THE UPDATE: exit 0 and exactly six numbered lines (Zip, Folder, Changed, Kept, Backup, Next)",
              rc == 0 and len(lines) == 6 and [ln.split()[1] for ln in lines] == ["Zip", "Folder", "Changed", "Kept", "Backup", "Next"], out)
        check("3. line 1 names the zip and 'SHA-256 OK'; line 3 '3 updated, 5 new, 6 already the same'; line 6 says the bot was NOT started",
              "OLYMPUS_BACKUP_2026-11-11_abc1234.zip  (SHA-256 OK)" in lines[0] and "3 updated, 5 new, 6 already the same" in lines[2] and "NOT started" in lines[5] and "requirements.txt changed" in lines[5], lines)
        check("3. changed code is the zip's: engine/lit.py, docs/NOTES.md, START_BOT.bat (CRLF kept), the new files with their folders",
              rb(os.path.join(bot, "engine", "lit.py")) == b"VERSION = 'new'\n" and rb(os.path.join(bot, "docs", "NOTES.md")) == b"new notes\n" and rb(os.path.join(bot, "START_BOT.bat")).endswith(b"v2\r\n")
              and rb(os.path.join(bot, "engine", "new_mod.py")) == b"NEW = True\n" and rb(os.path.join(bot, "docs", "deep", "a", "b", "c.md")) == b"deep\n" and rb(os.path.join(bot, "tools", "update_from_zip.py")) == rb(TOOL))
        check("3. a file that only differs by Windows line ends is left alone (README.md, engine/live.py keep their bytes)", after["README.md"] == before["README.md"] and after["engine/live.py"] == before["engine/live.py"])
        untouched = [k for k in LOCAL_ONLY if after.get(k) != before[k]]
        check(f"3. every local-only file is byte for byte the owner's ({len(LOCAL_ONLY)} files: alerts, tv, tv_device, autostart, live_state, memory.db, .env, .env.local, NinjaTrader bars, logs, gitignored switches)", not untouched, untouched)
        check("3. nothing the zip should not hold was written: no logs/evil.log, no data/nt_bars/evil.csv, no backups/x.txt, no .git/config, no data/live_state_atlas_v2.json",
              not any(k in after for k in ("logs/evil.log", "data/nt_bars/evil.csv", ".git/config", "data/live_state_atlas_v2.json")) and not os.path.exists(os.path.join(bot, "backups", "x.txt")))
        check("3. zip paths that try to leave the folder were skipped and said so: nothing in the parent folder, at the drive root or anywhere else",
              not os.path.exists(os.path.join(base, "evil_parent.txt")) and not os.path.exists(os.path.join(base, "evil_dots.txt")) and not os.path.exists("/abs_evil.txt") and not any("evil" in k for k in after) and "4 odd paths skipped" in lines[3], lines[3])
        check("3. live_model_lit.json differs from the zip's: the LOCAL one is kept (room_f 0.6) and line 4 says 'live_model_lit.json differ from the zip: YOURS kept'",
              rb(os.path.join(bot, "live_model_lit.json")).decode() == MODEL_LIT_LOCAL and "live_model_lit.json differ from the zip: YOURS kept" in lines[3], lines[3])
        check("3. live_model.json has the same values (other spacing, CRLF): not touched and not reported as different", after["live_model.json"] == before["live_model.json"] and "live_model.json " not in lines[3])
        check("3. nothing was deleted: the old folder's extra file (tools/old_tool.py) is still there", all(k in after for k in before), [k for k in before if k not in after])
        bdirs = sorted(os.listdir(os.path.join(bot, "backups", "update_from_zip")))
        bdir = os.path.join(bot, "backups", "update_from_zip", bdirs[-1])
        man = json.loads(rb(os.path.join(bdir, "manifest.json")))
        state = rb(os.path.join(bdir, "state_before.txt")).decode()
        check("3. the backup: one folder with state_before.txt (every file of the folder, size + time; logs / nt_bars only named), a copy of each replaced file with its old bytes, a manifest",
              len(bdirs) == 1 and "\tengine/lit.py" in state and "\tdata/alerts.json" in state and "logs/ (not listed)" in state and "LOCAL-SECRET" not in state
              and rb(os.path.join(bdir, "files", "engine", "lit.py")) == b"VERSION = 'old'\n" and rb(os.path.join(bdir, "files", "docs", "NOTES.md")) == b"old notes\n"
              and sorted(os.listdir(bdir)) == ["files", "manifest.json", "state_before.txt"], (bdirs, os.listdir(bdir), state[:300]))
        check("3. the manifest lists what was replaced, added and kept (and holds no file contents)",
              sorted(man["replaced"]) == ["START_BOT.bat", "docs/NOTES.md", "engine/lit.py"]
              and sorted(man["added"]) == ["UNDO_UPDATE.bat", "docs/deep/a/b/c.md", "engine/new_mod.py", "requirements.txt", "tools/update_from_zip.py"] and man["kept_model"] == ["live_model_lit.json"] and "data/alerts.json" in man["kept_local"] and man["done"] is True and "LOCAL-SECRET" not in json.dumps(man), man)

        # ---- twice
        rc, out = run([zp, "--folder", bot], home, port)
        check("3. run it again: 'nothing to do: 0 updated, 0 new', the kept live_model is named again, no second backup", rc == 0 and "nothing to do: 0 updated, 0 new" in out and "YOURS kept" in out
              and len(os.listdir(os.path.join(bot, "backups", "update_from_zip"))) == 1 and tree(bot) == after, out)

        # ---- undo
        rc, out = run(["--undo", "--folder", bot, "--dry-run"], home, port)
        check("3. undo, dry run: says 3 files back and 5 removed, changes nothing", rc == 0 and "would put back 3 files and remove 5 new ones" in out and tree(bot) == after, out)
        rc, out = run(["--undo", "--folder", bot], home, port)
        check("3. UNDO: exit 0, six lines, and the folder is byte for byte what it was before the update (the new files and their empty folders are gone)",
              rc == 0 and len(six_lines(out)) == 6 and "3 files put back, 5 new files removed" in out and tree(bot) == before and not os.path.exists(os.path.join(bot, "docs", "deep")), (out, {k for k in set(tree(bot)) ^ set(before)}))
        rc, out = run(["--undo", "--folder", bot], home, port)
        check("3. undo twice: 'Nothing to undo' (exit 2)", rc == 2 and "Nothing to undo" in out and tree(bot) == before, out)

        # ---- update again, the owner edits a new file, undo keeps it
        rc, out = run([zp, "--folder", bot], home, port)
        wr(os.path.join(bot, "engine", "new_mod.py"), "NEW = 'edited by the owner'\n")
        rc2, out2 = run(["--undo", "--folder", bot], home, port)
        t2 = tree(bot)
        check("3. undo after the owner edited a file the update had added: that file is kept and named, everything else is put back",
              rc == 0 and rc2 == 0 and "engine/new_mod.py" in out2 and "kept" in out2 and "engine/new_mod.py" in t2 and {k: v for k, v in t2.items() if k != "engine/new_mod.py"} == before, out2)
        os.remove(os.path.join(bot, "engine", "new_mod.py"))

        # ---- a write that fails rolls everything back
        badfiles = {**{k: v for k, v in ZIP_FILES.items() if "evil" not in k}, "tools/blocker/inner.py": "cannot be written: tools/blocker is a file\n"}
        zbad = make_zip(base, name="OLYMPUS_BACKUP_2026-11-12_fail000.zip", files=badfiles)
        rc, out = run([zbad, "--folder", bot], home, port)
        check("3. a file that cannot be written (the path is blocked): exit 1, 'Everything was put back', the folder is byte for byte as before, the bot's own files were never half-updated",
              rc == 1 and "could not be written" in out and "Everything was put back." in out and tree(bot) == before, (out, set(tree(bot)) ^ set(before)))

        # ---- found by itself in Downloads; the newest wins; six lines again
        dl = os.path.join(home, "Downloads")
        make_zip(base, name="OLYMPUS_BACKUP_2026-11-01_old0000.zip", files={**ZIP_FILES, "engine/lit.py": "VERSION = 'older'\n"}, where=dl)
        newest = make_zip(base, name="OLYMPUS_BACKUP_2026-11-11_abc1234.zip", where=dl)
        os.utime(os.path.join(dl, "OLYMPUS_BACKUP_2026-11-01_old0000.zip"), (SAT - 9e5, SAT - 9e5))
        os.utime(newest, (SAT, SAT))
        rc, out = run(["--folder", bot], home, port)
        check("3. no zip named: the newest OLYMPUS_BACKUP_*.zip in Downloads is used, checked (SHA-256 OK) and applied", rc == 0 and "OLYMPUS_BACKUP_2026-11-11_abc1234.zip  (SHA-256 OK)" in out and rb(os.path.join(bot, "engine", "lit.py")) == b"VERSION = 'new'\n", out)
        rc, out = run(["", "--folder", bot, "--dry-run"], home, port)
        check("3. an empty first argument (the .bat passes \"%~1\") is the same as none", rc == 0 and "nothing to do" in out, out)

        # ---- a zip without a .sha256.txt
        nosha = make_zip(base, name="OLYMPUS_BACKUP_2026-11-13_nosha00.zip", files={**ZIP_FILES, "engine/lit.py": "VERSION = 'newer'\n"}, sha="none", where=os.path.join(base, "dl2"))
        rc, out = run([nosha, "--folder", bot], home, port)
        check("3. a zip with no .sha256.txt next to it: applied, and line 1 says honestly 'SHA-256 not checked'", rc == 0 and "SHA-256 not checked (no .sha256.txt next to it)" in out and rb(os.path.join(bot, "engine", "lit.py")) == b"VERSION = 'newer'\n", out)
        check("3. backups are kept (at most 5) inside the bot folder's own gitignored backups folder", 1 <= len(os.listdir(os.path.join(bot, "backups", "update_from_zip"))) <= 5 and U.matches("backups/update_from_zip/x/manifest.json", U.ignore_patterns(GITIGNORE)))

        # ---- the .bat's first-run line: take the updater out of the zip
        bat = rb(os.path.join(ROOT, "UPDATE_FROM_ZIP.bat")).decode("ascii")
        m = re.search(r'-c "([^"]+)" "%TOOL%" "%CD%" %ARGS%', bat)
        check("3. UPDATE_FROM_ZIP.bat holds one python -c line for the first run (no double quote, percent sign or cmd special character inside it)", bool(m) and not re.search(r'[%&|<>^!]', m.group(1)), m and m.group(1))
        if m:
            old_bot = os.path.join(base, "oldbot")
            os.makedirs(old_bot)
            outp = os.path.join(base, "le_update_from_zip.py")
            env = {**os.environ, "HOME": home, "USERPROFILE": home}
            r = subprocess.run([sys.executable, "-X", "utf8", "-c", m.group(1), outp, old_bot], capture_output=True, text=True, env=env)
            check("3. first run (the old folder has no updater): the line takes tools/update_from_zip.py out of the newest zip in Downloads, byte for byte", r.returncode == 0 and rb(outp) == rb(TOOL), r.stderr[-300:])
            r = subprocess.run([sys.executable, "-X", "utf8", "-c", m.group(1), outp + "2", old_bot, zp], capture_output=True, text=True, env=env)
            check("3. ...or out of the zip dragged onto the .bat", r.returncode == 0 and rb(outp + "2") == rb(TOOL), r.stderr[-300:])
            empty = os.path.join(base, "emptyhome")
            os.makedirs(empty)
            r = subprocess.run([sys.executable, "-X", "utf8", "-c", m.group(1), outp + "3", old_bot], capture_output=True, text=True, env={**os.environ, "HOME": empty, "USERPROFILE": empty})
            check("3. ...and with no zip anywhere it fails (the .bat then prints the [FIX] line) and writes nothing", r.returncode != 0 and not os.path.exists(outp + "3"))
            # the taken-out updater, run from outside the repo against the fake folder
            r = subprocess.run([sys.executable, "-X", "utf8", outp, "--folder", bot, "--port", str(port), "--now", str(SAT), "--dry-run"], capture_output=True, text=True, env=env)
            check("3. the taken-out updater runs from a temp folder (outside the repo) with --folder", r.returncode == 0 and len(six_lines(r.stdout)) == 6, r.stdout + r.stderr)
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    test_static()
    test_units()
    test_flows()
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    sys.exit(1 if bad else 0)
