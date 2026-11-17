"""Owner's PC health check and daily helpers (read-only: never starts, stops, arms or routes anything).

  python -X utf8 -m engine.ops_checks              one screen of green / yellow / red checks, each with its one fix
                                                   (HEALTH_CHECK.bat)
  python -X utf8 -m engine.ops_checks --tick       the scheduled task (scripts/install_ops_task.ps1, every 5 min): whatever
                                                   is due now (pre-session check 01:40 ET, end-of-day 16:05 ET, weekly
                                                   Sunday evening, internet / NinjaTrader drop + recovery, MFFU inactivity,
                                                   eval passed / failed, contract roll, nightly backup + log rotation;
                                                   prop business: payout can be requested / time to buy the next eval
                                                   (tools/business.py), weekly rule-page + discount-code watch
                                                   (tools/prop_watch.py))
  python -X utf8 -m engine.ops_checks --presession | --eod | --weekly [--send]   build one of the phone notices now
                                                   (prints it; --send also pushes it)
  python -X utf8 -m engine.ops_checks --backup     back up the state files now (backups/, kept 14 days) + rotate logs/
  python -X utf8 -m engine.ops_checks --restore latest [--yes]   put the newest backup's state files back (dry run without
                                                   --yes; refused while the bot runs / a position is open; the files it
                                                   replaces are zipped first to backups/le-pre-restore-*.zip)
  python -X utf8 -m engine.ops_checks --update-guard   UPDATE.bat: exit 1 when a trade / setup is open (never update then),
                                                   exit 2 inside 01:50-16:00 ET on a weekday (ask first), else 0
  python -X utf8 -m engine.ops_checks --wait-server 90   wait until the dashboard answers (exit 1 if it never does)
  python -X utf8 -m engine.ops_checks --after-update     UPDATE.bat: quick self-tests + the health screen; exit 1 on a FIX
  python -X utf8 -m engine.ops_checks --translate "<error text>"   the plain-words fix for one error

Where the facts come from (no secrets read or printed, the live phrase is never written anywhere):
  * logs/heartbeat_last.json: the server's last heartbeat (engine/heartbeat.py writes it next to every push): the bot's own
    health block (account, LIVE/SIM, NinjaTrader connection, feed ages, kill) and the eval's P&L per day.
  * http://127.0.0.1:<PORT>/api/health/ping: is the dashboard server up, is the bot running, did the heartbeat push work.
  * NinjaTrader's folder (Documents\\NinjaTrader 8: incoming / outgoing / le_feed), read directly, so the check works with
    the bot stopped.
  * Windows settings through powercfg and the registry (read only). On another OS those lines say "Windows only".
Pushes go to the phone app (engine/push.py, kind "ops"), each one once (data/ops_state.json keeps the keys). LE_OPS_PUSH=0
turns the pushes off (the checks still run and log to logs/ops-YYYYMMDD.log).
"""
from __future__ import annotations

import datetime as dt
import email.utils
import glob
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
LOG_DIR = os.path.join(ROOT, "logs")
BACKUP_DIR = os.path.join(ROOT, "backups")                 # gitignored
STATE_PATH = os.path.join(DATA, "ops_state.json")         # gitignored: sent keys, drop timers, last backup
HB_LAST_PATH = os.path.join(LOG_DIR, "heartbeat_last.json")   # engine/heartbeat.py writes it
BACKUP_KEEP_DAYS = 14
LOG_GZIP_AFTER_DAYS = 1
LOG_DELETE_AFTER_DAYS = 30
AUDIT_KEEP_DAYS = 365                                       # logs/ninjatrader_oif*.gz: every order line ever written
AUDIT_ROLL_BYTES = 20 * 1024 * 1024
PLAN = {"target": 3000.0, "sessions": 10, "inactivity_days": 7, "warn_days": 5}
OWNER_PRICE = "$91.80"                                      # the owner's Builder 50K price with a discount code (2026-10-18)
PROBE_URLS = ("https://www.google.com/generate_204", "https://www.cloudflare.com/cdn-cgi/trace", "https://github.com")
OK, WARN, BAD, INFO, SKIP = "ok", "warn", "bad", "info", "skip"
_SAVE_KEYS = 400


def _port() -> int:
    try:
        return int(os.environ.get("PORT") or 8766)
    except ValueError:
        return 8766


def _et(t=None) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(time.time() if t is None else t), ET)


def trading_day(t) -> str:
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")      # 18:00 ET opens the next trading day


def market_open(t) -> bool:
    """CME Globex open: Sun 18:00 ET -> Fri 17:00 ET, daily break 17:00-18:00 (same rule as engine/live.market_open)."""
    e = _et(t)
    mod = e.hour * 60 + e.minute
    if e.weekday() == 5 or (e.weekday() == 6 and mod < 1080) or (e.weekday() == 4 and mod >= 1020):
        return False
    if 1020 <= mod < 1080:
        return False
    try:                                  # CME holiday closure / after an early halt (engine/cme_calendar.py)
        from .cme_calendar import halted
        return not halted(t)
    except Exception:
        return True


def _money(x) -> str:
    v = round(float(x or 0))
    return "$0" if v == 0 else f"{'+' if v > 0 else '-'}${abs(v):,.0f}"


def _phrase() -> str:
    try:
        from .tradovate import LIVE_PHRASE
        return LIVE_PHRASE
    except Exception:
        return ""


_PATHS = re.compile(r"[A-Za-z]:[\\/][^\s;,'\"()]*|/(?:home|Users|tmp|root|mnt|var)/[^\s;,'\"()]*")


def scrub(text, n: int = 200, paths: bool = True) -> str:
    """One line, no file paths (for the phone), never the live phrase."""
    s = str(text or "").replace("\r", " ").replace("\n", " ").strip()
    p = _phrase()
    if p:
        s = s.replace(p, "<your phrase>")
    s = re.sub(r"type exactly '[^']*'", "type your phrase", s)
    if paths:
        s = _PATHS.sub("<path>", s)
    return s[:n]


# ================================================================================================ friendly errors
# (pattern, what it means in plain words, the one fix). First match wins: keep the generic ones last.
ERRORS = [
    ("nt_folder", r"NinjaTrader folder not found|incoming NOT FOUND|ATI.*not enabled",
     "NinjaTrader's order folder is missing.",
     "NinjaTrader 8 > Tools > Options > Automated trading interface: tick 'AT Interface', then restart NinjaTrader."),
    ("feed", r"FEED STALE|bars missing or stale|NinjaTrader bars missing|no NinjaTrader bars",
     "NinjaTrader bars are not reaching the bot, so new entries are blocked.",
     "Open NinjaTrader: the MNQ chart with LE_BarFeed must stay open and the connection green (Connections menu)."),
    ("nt_disconnected", r"\bDISCONNECTED\b|connection lost|Connection Lost",
     "NinjaTrader lost its connection to the broker.",
     "NinjaTrader > Connections: connect your account's connection again; check the internet."),
    ("kill", r"kill switch",
     "The kill switch is on for today: no new orders.",
     "Nothing to do: it clears at the next session. Pressed by mistake? Start the bot again on the dashboard."),
    ("not_armed", r"not armed|confirm phrase missing|start the server with NINJATRADER_LIVE|LIVE account .* refused",
     "The eval account was not started: a safety lock is still closed.",
     "Start it yourself on the dashboard (eval account, Arm, your phrase); NINJATRADER_LIVE=1 must be in .env.local.ps1."),
    ("port", r"Address already in use|WinError 10048|already in use by another process|port \d+ (is already|taken)",
     "Another copy of the bot is already running.",
     "Double-click STOP BOT, wait 10 s, then START DASHBOARD."),
    ("module", r"ModuleNotFoundError|No module named|ImportError",
     "A Python package is missing.",
     "Double-click UPDATE (it runs pip install), or: python -m pip install -r requirements.txt"),
    ("git", r"would be overwritten|not a fast-forward|Not possible to fast-forward|dirty tree|have diverged",
     "The update could not apply: files in the bot folder were changed by hand.",
     "Don't edit files in the bot folder; ask Claude to clean it up (git status shows which files)."),
    ("internet", r"getaddrinfo failed|Name or service not known|Could not resolve host|Temporary failure in name resolution|"
     r"Network is unreachable|WinError 1005[01]|WinError 10065|Max retries exceeded|timed out|No route to host",
     "No internet (or it dropped for a moment).",
     "Check the Wi-Fi / router. The bot catches up when it is back; NinjaTrader must reconnect too."),
    ("clock", r"CERTIFICATE_VERIFY_FAILED|certificate verify failed|certificate is not yet valid",
     "Secure connections fail: usually the PC clock is wrong.",
     "Settings > Time & language > Date & time: 'Set time automatically' on, then 'Sync now'."),
    ("disk", r"No space left|disk full|WinError 112|not enough space on the disk",
     "The disk is full.",
     "Empty the Recycle Bin and run Settings > System > Storage > Cleanup recommendations."),
    ("permission", r"PermissionError|Access is denied|WinError 5\b|being used by another process|WinError 32",
     "Windows blocked a file (antivirus, OneDrive or another program has it open).",
     "Run HEALTH CHECK: the Controlled Folder Access and OneDrive lines say what to change; close Excel if it has a bot file open."),
    ("encoding", r"UnicodeEncodeError|UnicodeDecodeError|'charmap' codec",
     "A text-encoding problem in the console window.",
     "Start the bot with START DASHBOARD or UPDATE (they set UTF-8), not by typing python server.py."),
    ("state_file", r"JSONDecodeError|unreadable .* starting clean|state save failed",
     "A bot state file is damaged or could not be saved.",
     "The bot starts clean. If today's trades are missing, the backups\\ folder has last night's copy (ask Claude)."),
    ("heartbeat", r"\[heartbeat\] push failed|Authentication failed|could not read Username|Permission to .* denied|"
     r"Support for password authentication",
     "The PC can't send its heartbeat to GitHub (git sign-in), so the phone and the cloud can't see it.",
     "Open a terminal in the bot folder, type: git fetch, sign in when the window asks; then STOP BOT + START DASHBOARD."),
    ("memory", r"MemoryError|Unable to allocate",
     "The PC ran out of memory.",
     "Close other programs and browser tabs; restart the PC after 16:00 ET."),
    ("db", r"database is locked",
     "A database was busy.",
     "Usually passes by itself; if it repeats, STOP BOT then START DASHBOARD."),
    ("crash", r"Traceback \(most recent call last\)|Exception in thread",
     "The bot hit an unexpected error (it restarts itself).",
     "If it repeats, send the HEALTH CHECK screen to Claude."),
]
_ERR_RX = [(re.compile(p, re.I), what, fix) for _k, p, what, fix in ERRORS]
FIX = {k: fix for k, _p, _w, fix in ERRORS}


def translate(text) -> dict | None:
    """{"what", "fix", "text"} for a known error, else None. text = the line, scrubbed (no paths, never the phrase)."""
    if not text:
        return None
    s = str(text)
    for rx, what, fix in _ERR_RX:
        if rx.search(s):
            return {"what": what, "fix": fix, "text": scrub(s, 160)}
    return None


def scan_logs(log_dir: str = LOG_DIR, now=None, max_lines: int = 3000) -> list:
    """Known errors in today's logs (server-*.log, update-*.log): one row per kind {"what", "fix", "count", "last"}."""
    now = time.time() if now is None else now
    day = _et(now).strftime("%Y%m%d")
    rows: dict = {}
    for name in (f"server-{day}.log", f"update-{day}.log"):
        p = os.path.join(log_dir, name)
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()[-max_lines:]
        except OSError:
            continue
        for ln in lines:
            tr = translate(ln)
            if not tr:
                continue
            r = rows.setdefault(tr["what"], {"what": tr["what"], "fix": tr["fix"], "count": 0, "last": ""})
            r["count"] += 1
            r["last"] = tr["text"]
    return sorted(rows.values(), key=lambda r: -r["count"])


# ================================================================================================ small IO helpers
def _read_json(path) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            v = json.load(fh)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=str)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, path)


def load_state(path: str = STATE_PATH) -> dict:
    s = _read_json(path)
    s.setdefault("sent", {})
    return s


def save_state(s: dict, path: str = STATE_PATH):
    sent = s.get("sent") or {}
    if len(sent) > _SAVE_KEYS:
        s["sent"] = dict(sorted(sent.items(), key=lambda kv: kv[1])[-_SAVE_KEYS:])
    try:
        _write_json(path, s)
    except Exception:
        pass


def ops_log(text: str, log_dir: str | None = None):
    log_dir = log_dir or LOG_DIR
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {scrub(text, 600, paths=False)}"
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, f"ops-{time.strftime('%Y%m%d')}.log"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _run(args, timeout=20) -> tuple[int, str]:
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, creationflags=flags)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return -1, f"{e.__class__.__name__}: {e}"


def _reg(hive: str, key: str, value: str):
    """A registry value (read only), or None. Windows only."""
    if os.name != "nt":
        return None
    try:
        import winreg
        h = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[hive]
        with winreg.OpenKey(h, key) as k:
            return winreg.QueryValueEx(k, value)[0]
    except Exception:
        return None


def _reg_key_exists(hive: str, key: str) -> bool | None:
    if os.name != "nt":
        return None
    try:
        import winreg
        h = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[hive]
        with winreg.OpenKey(h, key):
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return None


def http_probe(url: str, timeout: float = 5.0) -> dict:
    """One HEAD request: {"ok", "date" (the server's clock, unix s, or None), "t0", "t1"}. No API key, nothing sent."""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "liquidity-engine-healthcheck"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = r.headers.get("Date")
    except urllib.error.HTTPError as e:            # any HTTP answer proves the internet works
        d = e.headers.get("Date") if e.headers else None
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}", "t0": t0, "t1": time.time()}
    t1 = time.time()
    try:
        dd = email.utils.parsedate_to_datetime(d).timestamp() if d else None
    except Exception:
        dd = None
    return {"ok": True, "date": dd, "t0": t0, "t1": t1}


def internet(probe=http_probe, urls=PROBE_URLS) -> dict:
    """{"up": bool, "drift_s": server clock - this PC's clock (median of the answers), "n": answers}."""
    res = [probe(u) for u in urls]
    up = [r for r in res if r.get("ok")]
    rows = sorted((r["date"] - (r["t0"] + r["t1"]) / 2.0, max(0.0, r["t1"] - r["t0"]) / 2.0) for r in up if r.get("date"))
    if not rows:
        return {"up": bool(up), "n": len(up), "drift_s": None, "unc_s": None}
    d, half_rtt = rows[len(rows) // 2]
    # unc_s: how far off this reading can be. The server stamps the reply somewhere inside the round trip (+/- half of it;
    # a slow or CPU-starved PC stretches the round trip, owner's Surface 2026-10-25: "5.0 s ahead" while polls took 30 s)
    # and the Date header is whole seconds (+1 s).
    return {"up": bool(up), "n": len(up), "drift_s": d, "unc_s": round(half_rtt + 1.0, 3)}


def ping_server(port: int | None = None, timeout: float = 3.0) -> dict | None:
    """The dashboard's /api/health/ping, or None when nothing answers."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port or _port()}/api/health/ping", timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def hb_last(path: str = HB_LAST_PATH) -> dict:
    """The server's last heartbeat payload ({} when the heartbeat is off or never ran)."""
    s = _read_json(path)
    pl = s.get("payload") if isinstance(s.get("payload"), dict) else {}
    if pl:
        pl = {**pl, "_saved_t": s.get("saved_t"), "_push": s.get("push")}
    return pl


def nt_folder() -> str:
    try:
        from .ninjatrader import default_folder
        return default_folder()
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Documents", "NinjaTrader 8")


# ================================================================================================ the checks
def _c(key, name, level, text, fix=""):
    return {"key": key, "name": name, "level": level, "text": text, "fix": fix if level in (WARN, BAD) else ""}


def check_nt_folder(folder: str) -> dict:
    inc, out = os.path.isdir(os.path.join(folder, "incoming")), os.path.isdir(os.path.join(folder, "outgoing"))
    if not os.path.isdir(folder):
        return _c("nt_folder", "NinjaTrader folder", BAD, "Documents\\NinjaTrader 8 not found",
                  "Install / open NinjaTrader 8 once on this Windows user (set NINJATRADER_FOLDER if Documents is elsewhere).")
    if not (inc and out):
        miss = " + ".join(n for n, ok in (("incoming", inc), ("outgoing", out)) if not ok)
        return _c("nt_folder", "NinjaTrader folder", BAD, f"{miss} missing (order interface off)", FIX["nt_folder"])
    return _c("nt_folder", "NinjaTrader folder", OK, "incoming + outgoing present (order interface on)")


def nt_connections(folder: str) -> dict:
    """{connection name: CONNECTED | DISCONNECTED} from outgoing/<connection>.txt (engine/ninjatrader.connection_files)."""
    from .ninjatrader import connection_files
    return connection_files(folder)


def check_nt_connection(conns: dict, now, folder: str | None = None) -> dict:
    """With folder: NinjaTrader's live accounts (accounts.csv) and live bars count as connected too, since a connection
    file is written only on a state change (engine/ninjatrader.connection_view, 2026-11-03)."""
    view = None
    if folder:
        from .ninjatrader import connection_view
        view = connection_view(conns, folder, now)
    up = [k for k, v in (conns or {}).items() if v == "CONNECTED"]
    if view and view.get("connected") and not up:
        return _c("nt_conn", "NinjaTrader connection", OK, "connected (" + ", ".join(view["via"]) + ")")
    if not conns:
        return _c("nt_conn", "NinjaTrader connection", WARN if market_open(now) else INFO,
                  "no connection file (NinjaTrader closed, or never connected since it started)",
                  "Open NinjaTrader 8 and connect your account (Connections menu).")
    if up:
        return _c("nt_conn", "NinjaTrader connection", OK, "connected: " + ", ".join(scrub(k, 40) for k in up[:3]))
    return _c("nt_conn", "NinjaTrader connection", BAD, "DISCONNECTED: " + ", ".join(scrub(k, 40) for k in list(conns)[:3]),
              FIX["nt_disconnected"])


def last_bar_t(path: str) -> int | None:
    """Open time (unix s) of the last bar in an LE_BarFeed CSV (time,o,h,l,c,v), or None."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 4096))
            tail = fh.read().decode("utf-8", errors="replace").strip().splitlines()
        for ln in reversed(tail):
            head = ln.split(",")[0].strip()
            if head.isdigit():
                return int(head)
    except OSError:
        return None
    return None


def check_feed(folder: str, minutes: int, now, root: str = "MNQ") -> dict:
    p = os.path.join(folder, "le_feed", f"{root}_{minutes}m.csv")
    name = f"Bar feed {minutes}m"
    if not os.path.exists(p):
        return _c(f"feed_{minutes}m", name, BAD if minutes in (1, 5) else WARN, f"le_feed\\{root}_{minutes}m.csv missing",
                  "NinjaTrader: open an MNQ chart and add the LE_BarFeed indicator (ninjatrader/SETUP.md).")
    t = last_bar_t(p)
    if t is None:
        return _c(f"feed_{minutes}m", name, BAD, "file has no bars", "Reload the MNQ chart in NinjaTrader (F5).")
    age = int(now - t - minutes * 60)
    if not market_open(now) or not market_open(now - 15 * 60):
        return _c(f"feed_{minutes}m", name, INFO, f"market closed; last bar {_et(t):%a %H:%M} ET")
    lim = 4 * 60 if minutes == 1 else 11 * 60
    if age > lim:
        return _c(f"feed_{minutes}m", name, BAD, f"last bar {age // 60} min old (FEED STALE: no new entries)", FIX["feed"])
    return _c(f"feed_{minutes}m", name, OK, f"fresh (last bar closed {max(0, age)} s ago)")


def check_open_file(folder: str, now, root: str = "MNQ") -> dict:
    p = os.path.join(folder, "le_feed", f"{root}_1m_open.csv")
    if not os.path.exists(p):
        return _c("feed_open", "1m open file", WARN, "le_feed\\MNQ_1m_open.csv missing (sizing waits for the 1m bar close)",
                  "Recompile LE_BarFeed in NinjaTrader (NinjaScript Editor > F5) and reload the chart.")
    age = int(now - os.path.getmtime(p))
    if market_open(now) and market_open(now - 15 * 60) and age > 5 * 60:
        return _c("feed_open", "1m open file", WARN, f"not updated for {age // 60} min",
                  "NinjaTrader: the chart with LE_BarFeed must be connected and receiving ticks.")
    return _c("feed_open", "1m open file", OK, f"updated {age} s ago" if market_open(now) else "present")


def check_disk(path: str = ROOT, usage=shutil.disk_usage) -> dict:
    try:
        free = usage(path).free / 1e9
    except Exception as e:
        return _c("disk", "Disk space", SKIP, f"could not read ({e.__class__.__name__})")
    if free < 2:
        return _c("disk", "Disk space", BAD, f"{free:.1f} GB free", FIX["disk"])
    if free < 10:
        return _c("disk", "Disk space", WARN, f"{free:.1f} GB free", "Free some space soon: Settings > System > Storage > Cleanup.")
    return _c("disk", "Disk space", OK, f"{free:.0f} GB free")


def check_data(summary=None) -> dict:
    """The data files the backtests and the live window read (tools/data_check.py: order, OHLC, gaps, spikes, rolls, 1m vs 5m,
    VIX/VXN cover). ~3 s."""
    try:
        if summary is None:
            from tools import data_check
            summary = data_check.summary
        lvl, txt = summary()
    except Exception as e:
        return _c("data", "Data files", SKIP, f"could not check ({e.__class__.__name__})")
    lv = {"ok": OK, "warn": WARN, "fix": BAD}.get(lvl, WARN)
    return _c("data", "Data files", lv, txt, "Run python -X utf8 tools/data_check.py for the details; a bad file comes back with "
              "a fresh TradingView export (tools/grab_tv_export.py).")


def check_clock(net: dict) -> dict:
    d = net.get("drift_s")
    if not net.get("up"):
        return _c("clock", "Clock", SKIP, "no internet: not checked")
    if d is None:
        return _c("clock", "Clock", SKIP, "no time answer from the internet")
    fix = FIX["clock"]
    if abs(d) > 30:
        return _c("clock", "Clock", BAD, f"PC clock {abs(d):.0f} s {'behind' if d > 0 else 'ahead'} of internet time", fix)
    if abs(d) > 2.5:
        return _c("clock", "Clock", WARN, f"PC clock {abs(d):.1f} s {'behind' if d > 0 else 'ahead'}", fix)
    return _c("clock", "Clock", OK, f"within {max(abs(d), 0.5):.1f} s of internet time")


def check_internet(net: dict) -> dict:
    if net.get("up"):
        return _c("internet", "Internet", OK, f"up ({net.get('n')} of {len(PROBE_URLS)} sites answered)")
    return _c("internet", "Internet", BAD, "no site answered", FIX["internet"])


def _powercfg_ac(sub: str, setting: str, run=_run):
    """The AC (plugged in) value of one power setting, or None. The last two hex numbers powercfg prints are AC, DC
    (locale independent)."""
    code, out = run(["powercfg", "/q", "SCHEME_CURRENT", sub, setting])
    if code != 0:
        return None
    hx = re.findall(r"0x[0-9a-fA-F]+", out)
    return int(hx[-2], 16) if len(hx) >= 2 else None


def check_power(run=_run, is_windows=None) -> dict:
    if not (os.name == "nt" if is_windows is None else is_windows):
        return _c("power", "Power / sleep", SKIP, "Windows only")
    sleep_s = _powercfg_ac("SUB_SLEEP", "STANDBYIDLE", run)
    hib_s = _powercfg_ac("SUB_SLEEP", "HIBERNATEIDLE", run)
    lid = _powercfg_ac("SUB_BUTTONS", "LIDACTION", run)
    if sleep_s is None and hib_s is None:
        return _c("power", "Power / sleep", SKIP, "powercfg could not be read")
    probs = []
    if sleep_s:
        probs.append(f"sleeps after {sleep_s // 60} min")
    if hib_s:
        probs.append(f"hibernates after {hib_s // 60} min")
    if lid:
        probs.append("closing the lid sleeps it")
    if probs:
        return _c("power", "Power / sleep", WARN, "plugged in, the PC " + ", ".join(probs) + " (the bot keeps it awake only while it runs)",
                  "Settings > System > Power: Sleep 'Never' when plugged in; Control Panel > Power Options > lid: 'Do nothing'.")
    return _c("power", "Power / sleep", OK, "never sleeps when plugged in")


def check_windows_update(now, reg=_reg, key_exists=_reg_key_exists, is_windows=None) -> dict:
    if not (os.name == "nt" if is_windows is None else is_windows):
        return _c("winupdate", "Windows Update", SKIP, "Windows only")
    reboot = key_exists("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired")
    if reboot:
        return _c("winupdate", "Windows Update", WARN, "a restart is pending: Windows may restart the PC by itself",
                  "Restart the PC yourself after 16:00 ET today (not during the night session).")
    until = reg("HKLM", r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings", "PauseUpdatesExpiryTime")
    try:
        u = dt.datetime.fromisoformat(str(until).replace("Z", "+00:00")).timestamp() if until else None
    except ValueError:
        u = None
    if u and u > now:
        days = int((u - now) // 86400)
        lvl = WARN if days < 3 else OK
        return _c("winupdate", "Windows Update", lvl, f"paused until {_et(u):%a %b %d} ({days} days)",
                  "Settings > Windows Update > Pause updates again (up to 5 weeks).")
    return _c("winupdate", "Windows Update", WARN, "not paused: an update can restart the PC during the night session",
              "Settings > Windows Update > Pause updates (up to 5 weeks); install them on a weekend.")


def check_onedrive(folder: str) -> dict:
    if "onedrive" in folder.lower():
        return _c("onedrive", "OneDrive", WARN, "the NinjaTrader folder is inside OneDrive (syncing can lock order files)",
                  "OneDrive > Settings > Sync and backup > Manage back up: turn off Documents (or pause syncing on trading days).")
    return _c("onedrive", "OneDrive", OK, "NinjaTrader folder is not synced by OneDrive")


def check_cfa(folder: str, reg=_reg, is_windows=None) -> dict:
    """Controlled Folder Access (Windows ransomware protection) blocks unknown apps (python) from writing into Documents."""
    if not (os.name == "nt" if is_windows is None else is_windows):
        return _c("cfa", "Controlled Folder Access", SKIP, "Windows only")
    base = r"SOFTWARE\Microsoft\Windows Defender\Windows Defender Exploit Guard\Controlled Folder Access"
    pol = r"SOFTWARE\Policies\Microsoft\Windows Defender\Windows Defender Exploit Guard\Controlled Folder Access"
    v = reg("HKLM", pol, "EnableControlledFolderAccess")
    v = reg("HKLM", base, "EnableControlledFolderAccess") if v is None else v
    can_write = None
    if os.path.isdir(folder):
        p = os.path.join(folder, f".le_write_test_{os.getpid()}.tmp")
        try:
            with open(p, "w") as fh:
                fh.write("x")
            os.remove(p)
            can_write = True
        except OSError:
            can_write = False
    fix = ("Windows Security > Virus & threat protection > Ransomware protection > Allow an app through Controlled folder "
           f"access > add {os.path.basename(sys.executable)} ({sys.executable}).")
    if can_write is False:
        return _c("cfa", "Controlled Folder Access", BAD, "this PC blocks Python from writing into the NinjaTrader folder", fix)
    if v == 1:
        return _c("cfa", "Controlled Folder Access", WARN if can_write is None else OK,
                  "on" + (", but Python may write the NinjaTrader folder" if can_write else ""), fix)
    return _c("cfa", "Controlled Folder Access", OK, "off" if v in (0, 2, None) else f"mode {v}")


def check_decimal(reg=_reg, is_windows=None) -> dict:
    if not (os.name == "nt" if is_windows is None else is_windows):
        return _c("decimal", "Decimal format", SKIP, "Windows only")
    d = reg("HKCU", r"Control Panel\International", "sDecimal")
    if d is None:
        return _c("decimal", "Decimal format", SKIP, "could not be read")
    if d != ".":
        return _c("decimal", "Decimal format", WARN, f"Windows writes decimals with '{d}' (NinjaTrader prices use '.')",
                  "Control Panel > Region > Additional settings: Decimal symbol '.', Digit grouping ','; restart NinjaTrader.")
    return _c("decimal", "Decimal format", OK, "'.' decimals")


def check_versions(run=_run) -> list:
    out = []
    v = sys.version_info
    out.append(_c("python", "Python", OK if v >= (3, 10) else BAD, f"{v.major}.{v.minor}.{v.micro}",
                  "Install Python 3.12 from python.org (tick 'Add to PATH'), then UPDATE."))
    code, txt = run(["git", "--version"])
    out.append(_c("git", "Git", OK if code == 0 else BAD, txt.strip()[:40] if code == 0 else "git not found",
                  "Install Git for Windows (git-scm.com), then UPDATE."))
    miss = []
    for mod in ("fastapi", "uvicorn", "pandas", "numpy", "cryptography", "tzdata"):
        try:
            __import__(mod)
        except Exception:
            miss.append(mod)
    out.append(_c("packages", "Python packages", BAD if miss else OK, ("missing: " + ", ".join(miss)) if miss else "installed",
                  FIX["module"]))
    return out


def check_auto() -> list:
    out = []
    try:
        from . import autoupdate
        u = autoupdate.status()
        ver = f"version {u.get('sha') or '?'} on {u.get('branch') or '?'}"
        if not u.get("on"):
            out.append(_c("autoupdate", "Auto-update", INFO, f"off ({ver}); UPDATE.bat updates by hand"))
        elif u.get("result") in ("failed", "rolled_back"):
            out.append(_c("autoupdate", "Auto-update", WARN, f"last update {u['result']}: {scrub(u.get('reason'), 100)} ({ver})",
                          "Double-click UPDATE and read the red line; send it to Claude if it repeats."))
        else:
            out.append(_c("autoupdate", "Auto-update", OK, f"on, last: {u.get('result') or 'not run yet'} ({ver})"))
        if u.get("branch") and u["branch"] != "main":
            out.append(_c("branch", "Code branch", WARN, f"the bot folder is on '{u['branch']}', not main",
                          "Ask Claude to switch it back to main (UPDATE only pulls main)."))
    except Exception as e:
        out.append(_c("autoupdate", "Auto-update", SKIP, f"status unavailable ({e.__class__.__name__})"))
    try:
        from . import autoresume
        r = autoresume.status()
        if r.get("on"):
            lvl = WARN if r.get("last_result") in ("refused", "failed") else OK
            out.append(_c("autoresume", "Auto-resume", lvl, f"on for {scrub(r.get('account'), 40)}"
                          + (f"; last {r['last_result']}: {scrub(r.get('last_reason'), 80)}" if r.get("last_result") else ""),
                          "Start the bot by hand on the dashboard; the reason above says what blocked it."))
        else:
            out.append(_c("autoresume", "Auto-resume", INFO, "off: after a restart you start the eval bot yourself"))
    except Exception as e:
        out.append(_c("autoresume", "Auto-resume", SKIP, f"status unavailable ({e.__class__.__name__})"))
    return out


def check_server(ping: dict | None) -> list:
    if ping is None:
        return [_c("server", "Bot server", BAD, f"the dashboard (port {_port()}) does not answer",
                   "Double-click START DASHBOARD (it starts the bot server).")]
    out = [_c("server", "Bot server", OK, f"up for {int(ping.get('uptime_s') or 0) // 60} min")]
    if not ping.get("bot_running"):
        out.append(_c("bot", "Bot", BAD, "server up, bot STOPPED", "Dashboard > Start (on your eval account)."))
    else:
        out.append(_c("bot", "Bot", OK, "running"))
    return out


def check_heartbeat(ping: dict | None, hb: dict, now) -> dict:
    h = (ping or {}).get("heartbeat") or {}
    if ping is not None and not h.get("enabled"):
        return _c("heartbeat", "Heartbeat to the cloud", WARN, "off: the phone and the cloud can't see this PC",
                  "Start the bot with START DASHBOARD / run_bot.ps1 (it turns the heartbeat on).")
    last = h.get("last") or (hb.get("_push") or {})
    at = last.get("at") or hb.get("_saved_t")
    if not at:
        return _c("heartbeat", "Heartbeat to the cloud", WARN if ping else INFO, "no heartbeat sent yet",
                  "Wait 5 min after the bot starts; if it stays, run HEALTH CHECK again.")
    age = int(now - float(at))
    if last.get("ok") is False:
        tr = translate("[heartbeat] push failed " + str(last.get("error") or ""))
        return _c("heartbeat", "Heartbeat to the cloud", BAD, f"last push failed {age // 60} min ago: {scrub(last.get('error'), 80)}",
                  tr["fix"] if tr else FIX["heartbeat"])
    if age > 20 * 60:
        return _c("heartbeat", "Heartbeat to the cloud", WARN, f"last push {age // 60} min ago", "Restart the bot: STOP BOT, then START DASHBOARD.")
    fz = (h.get("health") or {}).get("frozen") if isinstance(h.get("health"), dict) else None
    if isinstance(fz, dict) and fz.get("to") and now - float(fz["to"]) < 24 * 3600 and float(fz.get("s") or 0) >= 15 * 60:
        # engine/heartbeat.py noticed the whole process stood still (2026-10-25/26: the Surface slept 22:43 -> 05:17 ET)
        s = int(fz["s"])
        return _c("heartbeat", "Heartbeat to the cloud", WARN,
                  f"last push {age // 60} min ago, but the PC was asleep {s // 3600} h {s % 3600 // 60} min "
                  f"({_et(fz['from']):%a %H:%M} -> {_et(fz['to']):%H:%M} ET): no bars, no trades, no heartbeat then",
                  "Settings > System > Power: Sleep 'Never' when plugged in; Control Panel > Power Options > lid: 'Do nothing'.")
    return _c("heartbeat", "Heartbeat to the cloud", OK, f"last push {age // 60} min ago")


def _hb_fresh(hb: dict, now, max_age=15 * 60) -> bool:
    return bool(hb) and now - float(hb.get("t") or 0) <= max_age


def check_account(hb: dict, now) -> list:
    """From the bot's own health block (heartbeat): which account, kill switch."""
    if not _hb_fresh(hb, now):
        return [_c("account", "Account", INFO, "unknown (no recent heartbeat from the bot)")]
    hl = hb.get("health") if isinstance(hb.get("health"), dict) else {}
    a = hl.get("account") or {}
    out = []
    label, name = a.get("label") or "?", scrub(a.get("name") or hb.get("adapter") or "?", 40)
    if hl.get("kill"):
        out.append(_c("kill", "Kill switch", BAD, "ON for today: no new orders", FIX["kill"]))
    if label == "LIVE":
        if a.get("enabled") is False:
            tr = translate(a.get("disabled")) or {"fix": FIX["not_armed"]}
            out.append(_c("account", "Account", BAD, f"{name}: orders DISABLED ({scrub(a.get('disabled'), 80)})", tr["fix"]))
        else:
            out.append(_c("account", "Account", OK, f"{name} (your eval, LIVE)"))
    elif label == "SIM":
        out.append(_c("account", "Account", WARN, f"orders go to {name} (Sim), not your eval",
                      "To trade the eval: dashboard > Stop, choose the eval account, Arm, type your phrase, Start."))
    else:
        out.append(_c("account", "Account", WARN, "paper only: no orders reach NinjaTrader",
                      "To trade the eval: dashboard > adapter NinjaTrader, the eval account, Arm, your phrase, Start."))
    return out


def check_backup(state: dict, now) -> dict:
    t = state.get("last_backup_t")
    if not t:
        return _c("backup", "Backup", INFO, "no backup yet (made every evening after 16:35 ET by the ops task)")
    age_h = (now - float(t)) / 3600
    if age_h > 36:
        return _c("backup", "Backup", WARN, f"last backup {age_h / 24:.1f} days ago",
                  "Install the helper task: double-click SETUP SHORTCUTS (it adds the 5-minute ops task).")
    return _c("backup", "Backup", OK, f"last backup {_et(t):%a %H:%M} ET ({state.get('last_backup_files', '?')} files)")


def check_logs(rows: list) -> list:
    out = []
    for r in rows[:4]:
        out.append(_c("log", "Log: " + r["what"].split(":")[0][:40], WARN, f"{r['count']}x today, last: {r['last'][:90]}", r["fix"]))
    if not rows:
        out.append(_c("log", "Logs", OK, "no known errors today"))
    return out


def gather(now=None, folder=None, ping=..., hb=None, net=None, state=None, light=False) -> dict:
    """Everything the checks read, once (tests pass their own)."""
    now = time.time() if now is None else now
    return {"now": now, "folder": folder or nt_folder(), "ping": ping_server() if ping is ... else ping,
            "hb": hb_last() if hb is None else hb, "net": (internet() if net is None else net),
            "state": load_state() if state is None else state, "light": light}


def run_checks(ctx: dict) -> list:
    now, folder = ctx["now"], ctx["folder"]
    checks = []
    checks += check_server(ctx["ping"])
    checks += check_account(ctx["hb"], now)
    checks.append(check_nt_folder(folder))
    checks.append(check_nt_connection(nt_connections(folder), now, folder))
    try:                                          # the chart the bot decides on: MNQ, or NQ with signal_root "NQ"
        from .ninjatrader import NinjaTraderBars
        root = NinjaTraderBars(folder).root_for("NQ") or "MNQ"
    except Exception:
        root = "MNQ"
    checks.append(check_feed(folder, 1, now, root=root))
    checks.append(check_feed(folder, 5, now, root=root))
    checks.append(check_open_file(folder, now, root=root))
    checks.append(check_internet(ctx["net"]))
    checks.append(check_clock(ctx["net"]))
    checks.append(check_heartbeat(ctx["ping"], ctx["hb"], now))
    checks.append(check_disk())
    try:                                          # account B readiness (engine/ai_watch.py, from the heartbeat's "ai" block)
        from . import ai_watch
        checks += ai_watch.ops_checks(ctx["hb"], now)
    except Exception:
        pass
    if not ctx.get("light"):
        checks.append(check_power())
        checks.append(check_windows_update(now))
        checks.append(check_onedrive(folder))
        checks.append(check_cfa(folder))
        checks.append(check_decimal())
        checks += check_versions()
        checks += check_auto()
        checks.append(check_backup(ctx["state"], now))
        checks.append(check_data())
        checks += check_logs(scan_logs(now=now))
    return checks


# ================================================================================================ the screen
_COL = {OK: "\033[92m", WARN: "\033[93m", BAD: "\033[91m", INFO: "\033[96m", SKIP: "\033[90m"}
_TAG = {OK: " OK ", WARN: "WARN", BAD: "FIX ", INFO: "INFO", SKIP: "SKIP"}


def _color_on() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    try:
        if not sys.stdout.isatty():
            return False
    except Exception:
        return False
    if os.name == "nt":
        os.system("")                     # turns on ANSI colors in the Windows console
    return True


def render(checks: list, color: bool | None = None, now=None) -> str:
    color = _color_on() if color is None else color
    end = "\033[0m" if color else ""
    lines = [f"Liquidity Engine health check  {_et(now):%a %b %d %H:%M} ET", ""]
    for c in checks:
        col = _COL.get(c["level"], "") if color else ""
        lines.append(f"{col}[{_TAG.get(c['level'], c['level'])}]{end} {c['name']:<26} {c['text']}")
        if c.get("fix"):
            lines.append(f"       {col}->{end} {c['fix']}")
    bad = sum(c["level"] == BAD for c in checks)
    warn = sum(c["level"] == WARN for c in checks)
    lines.append("")
    if bad:
        lines.append(f"{_COL[BAD] if color else ''}{bad} thing(s) to FIX (red), {warn} to look at (yellow).{end}")
    elif warn:
        lines.append(f"{_COL[WARN] if color else ''}No red. {warn} thing(s) to look at (yellow).{end}")
    else:
        lines.append(f"{_COL[OK] if color else ''}All green.{end}")
    return "\n".join(lines)


def summary(checks: list) -> dict:
    bad = [c for c in checks if c["level"] == BAD]
    return {"bad": len(bad), "warn": sum(c["level"] == WARN for c in checks),
            "first_fix": (f"{bad[0]['name']}: {bad[0]['fix']}" if bad else None)}


# ================================================================================================ account + eval facts
def account_view(hb: dict, now) -> dict:
    """The routed account's facts for the notices: {"name", "label", "is_live", "trades" (closed), "day_pnl", "eval",
    "position", "fresh"}. From the heartbeat's "acct" + "health" blocks (the bot's own numbers)."""
    acct = hb.get("acct") if isinstance(hb.get("acct"), dict) else {}
    hl = hb.get("health") if isinstance(hb.get("health"), dict) else {}
    a = hl.get("account") or {}
    ak = acct.get("account") or {}
    label = a.get("label") or {"LIVE ACCOUNT": "LIVE"}.get(ak.get("label"), ak.get("label")) or "?"
    out = {"name": scrub(a.get("name") or ak.get("name") or "?", 40), "label": label, "is_live": label == "LIVE",
           "trades": [t for t in acct.get("trades") or [] if isinstance(t, dict)], "day_pnl": float(acct.get("day_pnl") or 0.0),
           "position": acct.get("position"), "fresh": _hb_fresh(hb, now, 30 * 60), "eval": None}
    ev = acct.get("eval") or {}
    if ev.get("days") is not None:
        try:
            from . import accounts
            out["eval"] = accounts.eval_view(ev.get("days") or {}, ev.get("start"), trading_day(now), now=now,
                                             anchor=ev.get("anchor"))
        except Exception:
            out["eval"] = None
    return out


def mffu_check_notice(hb: dict, view: dict, now) -> dict | None:
    """17:05 ET each weekday: "Check MFFU: bot thinks balance $X, floor $Y" for LIT's account (+ extra accounts and account
    B), so the owner compares them with the MFFU dashboard and re-anchors when they differ (engine/eval_life --anchor).
    None when the bot's numbers are not known."""
    from . import eval_life
    rows = []
    ev = view.get("eval") or {}
    if ev.get("balance") is not None and ev.get("floor") is not None:
        rows.append({"name": view.get("name"), "balance": ev["balance"], "floor": ev["floor"], "room": ev.get("room"),
                     "to_target": ev.get("to_target"), "anchor": ev.get("anchor")})
    acct = hb.get("acct") if isinstance(hb.get("acct"), dict) else {}
    for sub in acct.get("accounts") or []:
        try:
            if not isinstance(sub, dict) or sub.get("error") or (sub.get("kind") or "eval") != "eval":
                continue
            se = sub.get("eval") or {}
            from . import accounts
            v = accounts.eval_view(se.get("days") or {}, se.get("start"), trading_day(now), now=now, plan=sub.get("plan_rules"),
                                   anchor=se.get("anchor"))
            rows.append({"name": (sub.get("account") or {}).get("name") or sub.get("name"), "balance": v["balance"],
                         "floor": v["floor"], "room": v["room"], "to_target": v["to_target"], "anchor": v.get("anchor")})
        except Exception:
            continue
    try:
        ab = (((hb.get("second") or {}).get("route") or {}).get("account_b") or {})
        be = ab.get("eval") or {}
        if be.get("balance") is not None and be.get("floor") is not None:
            rows.append({"name": ab.get("account") or "account B", "balance": be["balance"], "floor": be["floor"],
                         "room": be.get("room"), "to_target": be.get("to_target"), "anchor": be.get("anchor")})
    except Exception:
        pass
    p = eval_life.anchor_check_payload(rows, now)
    if p:
        p["key"] = f"ops:mffu:{trading_day(now)}"
        if not view.get("fresh"):
            p["body"] = (p["body"] + " (bot numbers older than 30 min: is the PC bot running?)")[:900]
    return p


def eval_line(ev: dict | None) -> str:
    if not ev:
        return "Eval: no numbers yet."
    st = ev.get("status")
    if st == "passed" or (ev.get("to_target") is not None and ev["to_target"] <= 0):
        return f"Eval: PASSED (balance ${ev.get('balance', 0):,.0f})."
    if st == "failed" or (ev.get("room") is not None and ev["room"] <= 0):
        return f"Eval: FAILED (balance ${ev.get('balance', 0):,.0f})."
    s = f"Eval: {_money(ev.get('profit'))} so far, ${ev.get('to_target', 0):,.0f} to go"
    if ev.get("session"):
        s += f", session {ev['session']} of {ev.get('sessions') or PLAN['sessions']}"
    return s + f", room ${ev.get('room', 0):,.0f}."


def days_since_trade(view: dict, now, start: str | None = None) -> int | None:
    """Calendar days since the last trade on the account (or since the eval start when there is none yet)."""
    days = [str(t.get("day") or trading_day(t["entry_t"]))[:10] for t in view.get("trades") or [] if t.get("day") or t.get("entry_t")]
    if view.get("position"):
        return 0
    ref = max(days) if days else (str(start)[:10] if start else None)
    if not ref:
        return None
    try:
        return (_et(now).date() - dt.date.fromisoformat(ref)).days
    except ValueError:
        return None


def next_roll(today: dt.date) -> tuple[dt.date, str, str] | None:
    """(roll day, old contract, new contract) of the next quarterly roll (NinjaTrader names, engine/ninjatrader.nt_instrument)."""
    try:
        from .ninjatrader import nt_instrument
    except Exception:
        return None
    cur = nt_instrument("MNQ", today)
    for i in range(1, 120):
        d = today + dt.timedelta(days=i)
        n = nt_instrument("MNQ", d)
        if n != cur:
            return d, cur, n
    return None


# ================================================================================================ the notices
def _payload(sub: str, title: str, body: str, key: str, now) -> dict:
    from . import push
    p = push.text_payload("PC", "ops", scrub(title, 120, paths=True), scrub(body, 600, paths=True), key=key, t=int(now),
                          url="#/accounts")
    p["tag"] = f"le-ops-{sub}"
    return p


def presession_notice(checks: list, view: dict, now) -> dict:
    keys = ("server", "bot", "account", "kill", "nt_folder", "nt_conn", "feed_1m", "feed_5m", "internet", "clock", "disk", "heartbeat", "cfa",
            "acct_b")
    problems = [c for c in checks if c["key"] in keys and c["level"] == BAD]
    sim = [c for c in checks if c["key"] in ("account", "nt_conn") and c["level"] == WARN]   # Sim / paper, NinjaTrader closed
    day = trading_day(now)
    extra = _readiness(now)
    if not problems and not sim:
        body = f"Bot running on {view.get('name')}, NinjaTrader connected, bars fresh. {eval_line(view.get('eval'))}{extra}"
        return _payload("pre", "All green for tonight", body, f"ops:pre:{day}", now)
    first = (problems or sim)[0]
    more = len(problems) + len(sim) - 1
    title = "Fix before 02:00 ET: " + first["name"]
    body = f"{first['text']}. {first['fix']}" + (f" (+{more} more: double-click HEALTH CHECK)" if more > 0 else "") + extra
    return _payload("pre", title, body, f"ops:pre:{day}", now)


def _readiness(now, hb=None) -> str:
    """" News: ... Account B room ... Blocks on: ..." (engine/ai_watch.readiness_line). Never raises."""
    try:
        from . import ai_watch
        return " " + ai_watch.readiness_line(hb_last() if hb is None else hb, now)
    except Exception:
        return ""


def eod_notice(view: dict, now) -> dict:
    day = trading_day(now)
    today = [t for t in view.get("trades") or [] if str(t.get("day") or "")[:10] == day]
    pnl = sum(float(t.get("pnl") or 0) for t in today) if today else view.get("day_pnl") or 0.0
    if today:
        w = sum(float(t.get("pnl") or 0) > 0 for t in today)
        head = f"{len(today)} trade{'s' if len(today) != 1 else ''} ({w} won), {_money(pnl)}"
    else:
        head = "No trade today" + (f", {_money(pnl)}" if abs(pnl) >= 1 else "")
    body = f"{head} on {view.get('name')}. {eval_line(view.get('eval'))}"
    if not view.get("fresh"):
        body += " (bot numbers older than 30 min: is the PC bot running?)"
    return _payload("eod", f"Day summary {_et(now):%a %b %d}", body, f"ops:eod:{day}", now)


def weekly_notice(view: dict, state: dict, checks: list, now) -> dict:
    e = _et(now).date()
    mon = e - dt.timedelta(days=e.weekday())                 # Monday of this week (on Sunday: the week that just ended)
    fri = mon + dt.timedelta(days=4)
    wk = [t for t in view.get("trades") or [] if mon.isoformat() <= str(t.get("day") or "")[:10] <= fri.isoformat()]
    pnl = sum(float(t.get("pnl") or 0) for t in wk)
    w = sum(float(t.get("pnl") or 0) > 0 for t in wk)
    lo = sum(float(t.get("pnl") or 0) < 0 for t in wk)
    s = summary(checks)
    health = "PC all green" if not s["bad"] and not s["warn"] else f"PC: {s['bad']} to fix, {s['warn']} to look at (HEALTH CHECK)"
    pace = "on pace (2-4 a week)" if 2 <= len(wk) <= 4 else ("fewer than planned (normal some weeks)" if len(wk) < 2 else "busy week")
    body = (f"{len(wk)} trade{'s' if len(wk) != 1 else ''} ({w} won, {lo} lost), {_money(pnl)}: {pace}. "
            f"{eval_line(view.get('eval'))} {health}.")
    if state.get("last_backup_t"):
        body += f" Last backup {_et(state['last_backup_t']):%a}."
    try:                                          # the weekly self-review line (engine/ai_watch.py: drift, anomalies, rule changes)
        from . import ai_watch
        wl = ai_watch.weekly_line(hb_last())
        if wl:
            body += " " + wl
    except Exception:
        pass
    iso = f"{mon.isocalendar()[0]}-W{mon.isocalendar()[1]:02d}"
    return _payload("week", f"Week {mon:%b %d}-{fri:%b %d}", body, f"ops:week:{iso}", now)


def _idle_squeeze(now, n) -> dict | None:
    """engine/cme_calendar.idle_plan when a holiday leaves at most 1 CME session before the 7-day mark, else None."""
    if n is None:
        return None
    try:
        from . import cme_calendar as CC
        p = CC.idle_plan(_et(now).date() - dt.timedelta(days=int(n)), now, PLAN["inactivity_days"])
        return p if p["squeeze"] else None
    except Exception:
        return None


def inactivity_notice(view: dict, now) -> dict | None:
    ev = view.get("eval") or {}
    if not view.get("is_live") or ev.get("status") in ("passed", "failed"):
        return None
    n = days_since_trade(view, now, ev.get("start"))
    sq = _idle_squeeze(now, n)                 # a holiday week: at most 1 CME session left before the 7-day mark (cme_calendar)
    if n is None or (n < PLAN["warn_days"] and not sq):
        return None
    left = PLAN["inactivity_days"] - n
    title = f"No trade for {n} days (MFFU closes an account at {PLAN['inactivity_days']})"
    body = ("Place 1 MNQ by hand today (in and out, a few dollars), or let the min-days 1-micro trade run. "
            + (f"{left} day{'s' if left != 1 else ''} left." if left > 0 else "Do it today.")
            + (f" Holiday week: the last CME session before the 7-day mark is {sq['last_session']}." if sq and sq.get("last_session") else ""))
    return _payload("idle", title, body, f"ops:idle:{trading_day(now)}", now)


def eval_result_notice(view: dict, now) -> dict | None:
    ev = view.get("eval") or {}
    if not view.get("is_live") or not ev:
        return None
    start = ev.get("start") or "nostart"
    passed = ev.get("status") == "passed" or (ev.get("to_target") is not None and ev.get("to_target") <= 0 and ev.get("profit", 0) > 0)
    failed = ev.get("status") == "failed" or (ev.get("room") is not None and ev.get("room") <= 0)
    if passed:
        body = ("Next: 1) the bot stops trading this eval by itself; do not trade it more. 2) Next morning check MFFU shows "
                "it passed; if not, place one 1-MNQ trade (minimum days). 3) Sign MFFU's funded agreement. 4) Note the funded "
                "account Name in NinjaTrader. 5) Add it with funded sizing: python -X utf8 -m engine.eval_life --to-funded "
                "--account \"<Name>\" --start <first funded day>, restart the bot. 6) Payouts: ask once the balance is $53,600+ "
                "($1,500 above the $2,100 buffer), up to $2,000.")
        return _payload("eval", f"EVAL PASSED: {_money(ev.get('profit'))}", body, f"ops:eval:passed:{start}", now)
    if failed:
        body = (f"Next: 1) Stop the bot on this account. 2) Buy a new MFFU Builder 50K with your discount code (you paid "
                f"{OWNER_PRICE}; check for a current code first, verify it at checkout). 3) Tell Claude the new account name and its first session "
                "(eval_start). Stagger rule: if you run two evals, start the second 5 sessions after the first, never the "
                "same day (same trades, same result).")
        return _payload("eval", "Eval failed: max loss reached", body, f"ops:eval:failed:{start}", now)
    return None


def bot_pushes_eval(hb: dict, view: dict) -> bool:
    """True when the running PC bot sends the eval pass / fail notice itself (heartbeat health.eval_life, engine/eval_life.py)
    and its heartbeat is fresh: the scheduled task then stays quiet (the fallback for an older or stopped bot)."""
    hl = (hb or {}).get("health") if isinstance((hb or {}).get("health"), dict) else {}
    return bool((hl.get("eval_life") or {}).get("pushes") and view.get("fresh"))


def roll_notice(now) -> dict | None:
    today = _et(now).date()
    r = next_roll(today)
    if not r:
        return None
    day, old, new = r
    n = (day - today).days
    if n > 7 or n < 1:
        return None
    eve = day - dt.timedelta(days=1)
    when = "tomorrow" if n == 1 else f"in {n} days"
    body = (f"Orders switch to {new} by themselves on {day:%a %b %d}. You switch the chart: on {eve:%a %b %d} after 16:00 ET open "
            f"the NinjaTrader chart with LE_BarFeed, type {new} as its instrument, Data Series > Days to load 30, OK. "
            "Check LE_BarFeed is still on it, then run HEALTH CHECK (bar feed green).")
    return _payload("roll", f"Contract roll {when}: {old} -> {new}", body, f"ops:roll:{new}:{'tomorrow' if n == 1 else 'week'}", now)


def roll_late_notice(now, folder: str | None = None) -> dict | None:
    """On and after the roll day, the LE_BarFeed chart still on the old contract (engine/roll_watch.py; the adapter sends
    no new entry then): one push per trading day, before the session (the 01:40 ET daily run)."""
    try:
        from . import roll_watch
        n = roll_watch.late_notice(roll_watch.fact(folder or nt_folder(), now=now), now)
    except Exception:
        return None
    return _payload("roll", n["title"], n["body"], n["key"], now) if n else None


def watch(ctx: dict, state: dict, now) -> list:
    """Internet / NinjaTrader drops: one notice when it goes (NinjaTrader: after 2 checks in a row), one when it is back.
    The internet notice can only go out once it is back, so it says how long it was down."""
    out = []
    net = ctx["net"]
    if not net.get("up"):
        state.setdefault("net_down_since", int(now))
    elif state.get("net_down_since"):
        t0 = int(state.pop("net_down_since"))
        mins = int((now - t0) // 60)
        if mins >= 3:
            out.append(_payload("net", f"Internet was down {mins} min",
                                f"From {_et(t0):%H:%M} to {_et(now):%H:%M} ET. It's back. "
                                "Check NinjaTrader shows connected and the bot is running (HEALTH CHECK).", f"ops:net:{t0}", now))
    conns = nt_connections(ctx["folder"])
    watch_hours = _et(now).weekday() < 5 and 90 <= _et(now).hour * 60 + _et(now).minute <= 16 * 60 + 30
    down = bool(conns) and not any(v == "CONNECTED" for v in conns.values())
    if down:
        try:                    # a stale DISCONNECTED file next to a live connection with no file: not down (connection_view)
            from .ninjatrader import connection_view
            down = connection_view(conns, ctx["folder"], now).get("connected") is False
        except Exception:
            pass
    if down and net.get("up"):
        state["nt_down_n"] = int(state.get("nt_down_n") or 0) + 1
        state.setdefault("nt_down_since", int(now))
        if state["nt_down_n"] >= 2 and watch_hours and not state.get("nt_alerted"):
            state["nt_alerted"] = int(now)
            out.append(_payload("nt", "NinjaTrader disconnected",
                                f"Since {_et(state['nt_down_since']):%H:%M} ET. " + FIX["nt_disconnected"]
                                + (" A trade is open: check it in NinjaTrader now." if (ctx.get("hb") or {}).get("position") else ""),
                                f"ops:nt:down:{state['nt_down_since']}", now))
    elif not down and conns:
        if state.get("nt_alerted"):
            t0 = int(state.get("nt_down_since") or state["nt_alerted"])
            out.append(_payload("nt", "NinjaTrader reconnected", f"Back after {int((now - t0) // 60)} min ({_et(now):%H:%M} ET).",
                                f"ops:nt:up:{t0}", now))
        for k in ("nt_down_n", "nt_down_since", "nt_alerted"):
            state.pop(k, None)
    return out


# ================================================================================================ backup + log rotation
def backup_sources(root: str = ROOT) -> list:
    """State files worth keeping (no secrets: no push keys, no .env, no TradingView / alert credentials)."""
    d = os.path.join(root, "data")
    pats = ["live_state.json", "ninjatrader_state*.json", "*ledger*.json*", "lit_journal.jsonl", "lit_learning.json",
            "autostart.json", "autoupdate.json", "auto_resume.json", "ops_state.json", "nt_bars/*",
            "guards_state.json", "live_state_acctb.json", "*_guards.json", "ai_watch.json", "entry_pause.json", "presence.jsonl"]
    out = []
    for p in pats:
        out += [f for f in glob.glob(os.path.join(d, p)) if os.path.isfile(f)]
    return sorted(set(out))


def backup(root: str = ROOT, dest: str = BACKUP_DIR, keep_days: int = BACKUP_KEEP_DAYS, now=None) -> dict:
    """backups/le-backup-YYYYMMDD-HHMM.zip of backup_sources(); zips older than keep_days deleted. Never raises."""
    now = time.time() if now is None else now
    try:
        os.makedirs(dest, exist_ok=True)
        name = os.path.join(dest, f"le-backup-{_et(now):%Y%m%d-%H%M}.zip")
        files = backup_sources(root)
        tmp = name + ".part"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:
                try:
                    z.write(f, os.path.relpath(f, root))
                except OSError:
                    pass
        from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
        _fs_replace(tmp, name)
        gone = 0
        for old in glob.glob(os.path.join(dest, "le-backup-*.zip")):
            if now - os.path.getmtime(old) > keep_days * 86400:
                try:
                    os.remove(old)
                    gone += 1
                except OSError:
                    pass
        return {"ok": True, "file": os.path.basename(name), "files": len(files), "deleted": gone,
                "mb": round(os.path.getsize(name) / 1e6, 1)}
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def latest_backup(dest: str = BACKUP_DIR) -> str | None:
    z = sorted(glob.glob(os.path.join(dest, "le-backup-*.zip")), key=os.path.getmtime)
    return z[-1] if z else None


def restore(src: str, root: str = ROOT, yes: bool = False, ping=..., dest: str = BACKUP_DIR, now=None, hb=None) -> dict:
    """Put a backup zip's state files back (data/ only, the backup_sources() names). Dry run unless yes=True. Refused while
    the bot runs or a position is open (stop the bot first), and the files it replaces are zipped first
    (backups/le-pre-restore-*.zip). Never raises."""
    import fnmatch
    try:
        src = latest_backup(dest) if src in (None, "", "latest") else src
        if not src or not os.path.isfile(src):
            return {"ok": False, "error": "no backup zip found (backups/le-backup-*.zip)"}
        pats = [os.path.join("data", p).replace("\\", "/") for p in ("live_state.json", "ninjatrader_state*.json", "*ledger*.json*",
                "lit_journal.jsonl", "lit_learning.json", "autostart.json", "autoupdate.json", "auto_resume.json", "ops_state.json",
                "nt_bars/*", "guards_state.json", "live_state_acctb.json", "*_guards.json", "ai_watch.json", "entry_pause.json",
                "presence.jsonl")]
        with zipfile.ZipFile(src) as z:
            names = [n for n in z.namelist() if not n.endswith("/")]
            ok_names = [n for n in names if ".." not in n and not n.startswith("/") and any(fnmatch.fnmatch(n.replace("\\", "/"), p) for p in pats)]
            plan = {"ok": True, "zip": os.path.basename(src), "files": ok_names, "skipped": sorted(set(names) - set(ok_names)), "applied": False}
            if not yes:
                plan["text"] = f"dry run: {len(ok_names)} file(s) would be restored; add --yes to apply (stop the bot first)"
                return plan
            p = ping_server() if ping is ... else ping
            if p and (p.get("bot_running") or p.get("running")):
                return {**plan, "ok": False, "error": "the bot is running: stop it first (Bot page > Stop), then restore"}
            hb = hb_last() if hb is None else hb
            if hb.get("position"):
                return {**plan, "ok": False, "error": "the last heartbeat shows an open position: flatten / stop first"}
            os.makedirs(dest, exist_ok=True)
            pre = os.path.join(dest, f"le-pre-restore-{_et(now or time.time()):%Y%m%d-%H%M%S}.zip")
            with zipfile.ZipFile(pre, "w", zipfile.ZIP_DEFLATED) as zp:
                for n in ok_names:
                    f = os.path.join(root, n)
                    if os.path.isfile(f):
                        zp.write(f, n)
            for n in ok_names:
                f = os.path.join(root, n)
                os.makedirs(os.path.dirname(f), exist_ok=True)
                tmp = f + ".restore"
                with z.open(n) as fh, open(tmp, "wb") as out:
                    shutil.copyfileobj(fh, out)
                from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
                _fs_replace(tmp, f)
        ops_log(f"restore {os.path.basename(src)}: {len(ok_names)} files (previous copies in {os.path.basename(pre)})")
        return {**plan, "applied": True, "pre_restore": os.path.basename(pre),
                "text": f"restored {len(ok_names)} file(s); the replaced ones are in backups/{os.path.basename(pre)}"}
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def rotate_logs(log_dir: str = LOG_DIR, now=None) -> dict:
    """Compress *.log files untouched for a day (.log.gz), delete .gz older than 30 days (the order audit: 365), and roll
    the never-ending order audit (ninjatrader_oif.log) into a dated .gz once it passes 20 MB. Never raises."""
    now = time.time() if now is None else now
    res = {"gzipped": 0, "deleted": 0, "rolled": 0}
    try:
        for p in glob.glob(os.path.join(log_dir, "*.log")):
            try:
                age = now - os.path.getmtime(p)
                base = os.path.basename(p)
                if base.startswith("ninjatrader_oif"):
                    if os.path.getsize(p) > AUDIT_ROLL_BYTES and age > 60:
                        with open(p, "rb") as src, gzip.open(os.path.join(log_dir, f"ninjatrader_oif-{_et(now):%Y%m%d-%H%M}.log.gz"), "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        open(p, "w").close()
                        res["rolled"] += 1
                    continue
                if age > LOG_GZIP_AFTER_DAYS * 86400:
                    with open(p, "rb") as src, gzip.open(p + ".gz", "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    os.remove(p)
                    res["gzipped"] += 1
            except OSError:
                continue
        for p in glob.glob(os.path.join(log_dir, "*.gz")):
            keep = AUDIT_KEEP_DAYS if os.path.basename(p).startswith("ninjatrader_oif") else LOG_DELETE_AFTER_DAYS
            try:
                if now - os.path.getmtime(p) > keep * 86400:
                    os.remove(p)
                    res["deleted"] += 1
            except OSError:
                continue
        res["narrator"] = rotate_feed(os.path.join(log_dir, "narrator"), now=now)
    except Exception as e:
        res["error"] = f"{e.__class__.__name__}"
    return res


NARRATOR_GZIP_AFTER_DAYS = 3                                # logs/narrator/<day>.jsonl: one plain-language feed a day
NARRATOR_DELETE_AFTER_DAYS = 120


def rotate_feed(folder: str, now=None, gzip_after: int = NARRATOR_GZIP_AFTER_DAYS, delete_after: int = NARRATOR_DELETE_AFTER_DAYS) -> dict:
    """2026-10-29 (disk growth): the narrator's daily feeds (logs/narrator/<day>.jsonl, written every poll, never cut) are
    gzipped once untouched for 3 days and deleted after 120. The bot only reads today's file. Never raises."""
    now = time.time() if now is None else now
    out = {"gzipped": 0, "deleted": 0}
    try:
        for p in glob.glob(os.path.join(folder, "*.jsonl")):
            try:
                if now - os.path.getmtime(p) > gzip_after * 86400:
                    with open(p, "rb") as src, gzip.open(p + ".gz", "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    os.remove(p)
                    out["gzipped"] += 1
            except OSError:
                continue
        for p in glob.glob(os.path.join(folder, "*.jsonl.gz")):
            try:
                if now - os.path.getmtime(p) > delete_after * 86400:
                    os.remove(p)
                    out["deleted"] += 1
            except OSError:
                continue
    except Exception as e:
        out["error"] = f"{e.__class__.__name__}"
    return out


def backup_due(state: dict, now) -> bool:
    """Once a day after 16:35 ET (the bot is flat by 15:55), or whenever the last one is over 26 h old outside 01:50-16:00."""
    e = _et(now)
    mod = e.hour * 60 + e.minute
    last = float(state.get("last_backup_t") or 0)
    if _et(last).date() == e.date() and last:
        return False
    if mod >= 16 * 60 + 35:
        return True
    blackout = e.weekday() < 5 and 110 <= mod < 960
    return not blackout and now - last > 26 * 3600


def calendar_due(state: dict, now) -> bool:
    """The official news calendar refresh: once a day after 16:35 ET (after the backup), any day."""
    e = _et(now)
    return e.hour * 60 + e.minute >= 16 * 60 + 35 and state.get("last_calendar_day") != e.date().isoformat()


def backlog_notices(state: dict, now, runner=None) -> list:
    """Sunday: re-check the research watch-list once per ISO week (tools/backlog_recheck.py, ~10-90 s; result in
    logs/backlog_check.json) and return a notice for each lead that crossed its adopt bar (key per lead + data version, so
    one push each). Never raises; a failure is logged and retried next Sunday."""
    wk = "%d-W%02d" % _et(now).isocalendar()[:2]
    if state.get("backlog_wk") == wk:
        return []
    state["backlog_wk"] = wk
    try:
        if runner is None:
            from tools import backlog_recheck as BR
            res = BR.score_all(log=lambda *_: None)
            os.makedirs(os.path.dirname(BR.LOCAL), exist_ok=True)
            with open(BR.LOCAL, "w", encoding="utf-8") as fh:
                json.dump(res, fh, indent=1)
            out = BR.notices(res, now)
        else:
            out = runner(now)
        n = sum(1 for _ in out)
        ops_log(f"backlog re-check {wk}: {n} lead(s) crossed their bar")
        state["backlog_last"] = {"wk": wk, "t": int(now), "crossed": n}
        return out
    except Exception as e:
        ops_log(f"backlog re-check {wk} failed: {e.__class__.__name__}: {scrub(str(e), 160)}")
        return []


# ================================================================================================ sending + the tick
def send(payload: dict, state: dict, sender=None) -> dict:
    """Push once by key (state["sent"]); LE_OPS_PUSH=0: record only. sender(payload) -> result, for tests."""
    k = payload["key"]
    if k in state["sent"]:
        return {"dup": True, "key": k}
    state["sent"][k] = int(time.time())
    ops_log(f"notice {k}: {payload['title']} | {payload['body']}")
    if os.environ.get("LE_OPS_PUSH") == "0":
        return {"sent": 0, "skipped": "LE_OPS_PUSH=0", "key": k}
    try:
        if sender is not None:
            r = sender(payload)
        else:
            from . import push
            r = push.pc_send_now(payload)
    except Exception as e:
        r = {"sent": 0, "error": e.__class__.__name__}
    if not r.get("sent") and (r.get("errors") or r.get("error")) and not r.get("skipped"):
        state["sent"].pop(k, None)          # the push failed (network): try again on the next run while the window is open
    return r


def due(now) -> dict:
    """Which timed notices are in their window now (ET)."""
    e = _et(now)
    mod, wd = e.hour * 60 + e.minute, e.weekday()
    try:                                       # 2026-10-29: no session on a CME full closure (Christmas, New Year's Day):
        from .cme_calendar import full_closure  # no pre-session / day-summary push that day (only noise: "feed stale" ...)
        if wd < 5 and full_closure(e.date()):
            wd = 7
    except Exception:
        pass
    return {"presession": wd < 5 and 100 <= mod <= 135,            # 01:40-02:15 ET
            "eod": wd < 5 and 965 <= mod <= 1020,                   # 16:05-17:00 ET
            "weekly": wd == 6 and 1020 <= mod <= 1439,              # Sunday 17:00-23:59 ET
            "mffu_check": wd < 5 and 1025 <= mod <= 1075,           # 17:05-17:55 ET: "Check MFFU: bot thinks ..."
            "daily": (wd < 5 and (100 <= mod <= 135 or 965 <= mod <= 1020)) or (wd == 6 and 1020 <= mod <= 1439)}


def business_notices(view: dict, now) -> list:
    """The prop-business reminders (tools/business.py): a funded account can request a payout, time to buy the next eval.
    Each pushed once by its key. Never raises."""
    try:
        from tools import business
        return [_payload(n["sub"], n["title"], n["body"], n["key"], now) for n in business.notices(now, pc_eval=view.get("eval"))]
    except Exception as e:
        ops_log(f"business notices failed: {e.__class__.__name__}: {scrub(str(e), 120)}")
        return []


def watch_notices(state: dict, now) -> list:
    """Weekly (Sunday evening window, once per ISO week): the firms' rule pages and discount codes (tools/prop_watch.py).
    Fetch failures (DNS, 403, timeout) are recorded there and never push. Never raises."""
    try:
        from tools import prop_watch
        return [_payload(n["sub"], n["title"], n["body"], n["key"], now) for n in prop_watch.weekly(now, state)]
    except Exception as e:
        ops_log(f"prop watch failed: {e.__class__.__name__}: {scrub(str(e), 120)}")
        return []


def tick(now=None, ctx=None, state=None, sender=None, state_path: str = STATE_PATH, do_backup=True) -> list:
    """One scheduled run: every notice that is due, sent once. Returns the results."""
    now = time.time() if now is None else now
    state = load_state(state_path) if state is None else state
    D = due(now)
    full = D["presession"] or D["weekly"]
    real = ctx is None                       # the scheduled run gathers its own facts; a ctx handed in is a replay / test:
    ctx = ctx or gather(now, state=state, light=not full)    # no business reminders and no weekly web fetches then
    out = []
    try:
        notes = watch(ctx, state, now)
        view = account_view(ctx["hb"], now)
        if D["presession"] or D["eod"] or D["weekly"]:
            checks = run_checks(ctx)
            state["last_checks"] = {"t": int(now), **summary(checks)}
            if D["presession"]:
                notes.append(presession_notice(checks, view, now))
            if D["eod"]:
                notes.append(eod_notice(view, now))
            if D["weekly"]:
                notes.append(weekly_notice(view, state, checks, now))
                notes += backlog_notices(state, now)
        if D["daily"]:
            for n in (inactivity_notice(view, now), roll_notice(now), roll_late_notice(now, ctx.get("folder"))):
                if n:
                    notes.append(n)
            if real:
                notes += business_notices(view, now)
        if D["weekly"] and real:
            notes += watch_notices(state, now)
        if real:                       # a new MFFU account Name in NinjaTrader (engine/new_accounts.py): one push per Name
            try:
                from . import new_accounts
                notes += new_accounts.notices(now, folder=ctx.get("folder"))
            except Exception as e:
                ops_log(f"new account check failed: {e.__class__.__name__}")
        if D.get("mffu_check"):
            n = mffu_check_notice(ctx["hb"] or {}, view, now)
            if n:
                notes.append(n)
        n = eval_result_notice(view, now)
        if n and not bot_pushes_eval(ctx["hb"], view):
            notes.append(n)            # the running bot pushes its own pass / fail notice (engine/eval_life.py): no double push
        for p in notes:
            r = send(p, state, sender=sender)
            out.append({"key": p["key"], "title": p["title"], **{k: r.get(k) for k in ("sent", "dup", "skipped", "error")}})
        # critical alerts that repeat until "Got it" (the heartbeat's "crit"), the stale-cloud alarm, the app's levels
        # (engine/alerts_plus.py; a replay / test ctx only with its own relay_msgs / cloud_ref, never the network)
        try:
            from . import alerts_plus
            out += alerts_plus.ops_tick(ctx, state, now, lambda p: send(p, state, sender=sender), real)
        except Exception as e:
            ops_log(f"alerts plus failed: {e.__class__.__name__}: {scrub(str(e), 120)}")
        if do_backup and backup_due(state, now):
            b = backup(now=now)
            r = rotate_logs(now=now)
            ops_log(f"backup {b} logs {r}")
            if b.get("ok"):
                state["last_backup_t"], state["last_backup_files"] = int(now), b.get("files")
            out.append({"key": "backup", **b, "logs": r})
        if do_backup and real and calendar_due(state, now):
            state["last_calendar_day"] = _et(now).date().isoformat()      # once a day, even when every source fails
            try:                       # official Tier-1 calendar (engine/news_official.py): a failed source keeps its rows
                from . import news_official
                cal = news_official.refresh(log=lambda *a: None)
                ops_log(f"calendar {cal['ok']}/{len(news_official.SOURCES)} sources OK, events.csv "
                        f"{'updated' if cal['changed'] else 'unchanged'} (+{len(cal['added'])} / -{len(cal['removed'])})")
                out.append({"key": "calendar", "ok": cal["ok"], "changed": cal["changed"]})
            except Exception as e:
                ops_log(f"calendar refresh failed: {e.__class__.__name__}: {scrub(str(e), 120)}")
    finally:
        state["last_tick_t"] = int(now)
        save_state(state, state_path)
    return out


def hb_fields(state_path: str = STATE_PATH) -> dict:
    """Small block for the heartbeat ("ops"): the last check summary, the last backup, free disk. Never raises."""
    try:
        s = _read_json(state_path)
        lc = s.get("last_checks") or {}
        try:
            free = round(shutil.disk_usage(ROOT).free / 1e9, 1)
        except Exception:
            free = None
        try:                                     # the weekly rule-page / discount-code watcher, small (tools/prop_watch.py)
            from tools import prop_watch
            w = prop_watch.summary()
            watch = {"rules_t": w["rules"]["updated"], "rules_ok": w["rules"]["ok"], "rules_pages": w["rules"]["pages"],
                     "changes": [{k: c.get(k) for k in ("firm", "key", "seen")} for c in w["rules"]["changes"][:3]],
                     "codes_t": w["codes"]["updated"], "codes": [{k: c.get(k) for k in ("firm_name", "code", "off", "seen", "new")}
                                                                 for c in w["codes"]["rows"][:8]]}
        except Exception:
            watch = None
        return {"checks_t": lc.get("t"), "bad": lc.get("bad"), "warn": lc.get("warn"), "first_fix": scrub(lc.get("first_fix"), 160) or None,
                "backup_t": s.get("last_backup_t"), "tick_t": s.get("last_tick_t"), "disk_free_gb": free, "watch": watch}
    except Exception:
        return {}


# ================================================================================================ UPDATE.bat helpers
def update_guard(now=None) -> tuple[int, str]:
    """0 = fine to update; 1 = a trade / setup is open (never update now); 2 = inside 01:50-16:00 ET on a weekday."""
    now = time.time() if now is None else now
    try:
        from . import autoupdate
        flat = autoupdate.files_flat_reason(now=now)
    except Exception as e:
        flat = f"cannot tell if flat ({e.__class__.__name__})"
    hb = hb_last()
    if not flat and _hb_fresh(hb, now, 10 * 60):
        hl = hb.get("health") if isinstance(hb.get("health"), dict) else {}
        stage = (hl.get("lit") or {}).get("stage")
        if hb.get("position") or stage in ("limit", "cisd1m", "trade"):
            flat = "a LIT setup is armed or a trade is open" if stage != "trade" else "a trade is open"
    if flat:
        return 1, f"not flat: {scrub(flat, 120)}. Run UPDATE after the trade closes."
    e = _et(now)
    mod = e.hour * 60 + e.minute
    if e.weekday() < 5 and 110 <= mod < 960:
        return 2, "it is trading time (01:50-16:00 ET): updating restarts the bot. Best after 16:00 ET."
    return 0, "flat and outside trading time"


def wait_server(timeout_s: int = 90, port: int | None = None) -> bool:
    t_end = time.time() + timeout_s
    while time.time() < t_end:
        if ping_server(port, timeout=2) is not None:
            return True
        time.sleep(2)
    return False


def after_update() -> int:
    """Quick self-tests (the auto-update's own list) + the health screen. Exit 1 when anything is red."""
    color = _color_on()
    g, r, z = (_COL[OK], _COL[BAD], "\033[0m") if color else ("", "", "")
    fails = 0
    try:
        from .autoupdate import TESTS
    except Exception:
        TESTS = ()
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "LE_HEARTBEAT": "0", "LE_NO_AUTOSTART": "1"}
    for args in TESTS:
        try:
            r = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, timeout=600, env=env,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            code, out = r.returncode, (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            code, out = -1, f"{e.__class__.__name__}: {e}"
        name = " ".join(a for a in args if not a.startswith("-") and a != "utf8")
        if code == 0:
            print(f"{g}[ OK ]{z} self-test {name}")
        else:
            fails += 1
            tr = translate(out) or {"fix": "Send this screen to Claude."}
            print(f"{r}[FIX ]{z} self-test {name} FAILED\n       -> {tr['fix']}")
    checks = run_checks(gather())
    print(render(checks, color))
    return 1 if fails or summary(checks)["bad"] else 0


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.ops_checks", description="PC health check and daily helpers (read-only)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--tick", action="store_true")
    g.add_argument("--presession", action="store_true")
    g.add_argument("--eod", action="store_true")
    g.add_argument("--weekly", action="store_true")
    g.add_argument("--backup", action="store_true")
    g.add_argument("--update-guard", action="store_true")
    g.add_argument("--wait-server", type=int, metavar="SECONDS")
    g.add_argument("--after-update", action="store_true")
    g.add_argument("--translate", metavar="TEXT")
    g.add_argument("--restore", metavar="ZIP|latest", help="put a backup's state files back (dry run without --yes)")
    ap.add_argument("--yes", action="store_true", help="with --restore: apply it (the bot must be stopped)")
    ap.add_argument("--send", action="store_true", help="with --presession / --eod / --weekly: push it too")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.tick:
        res = tick()
        ops_log(f"tick: {json.dumps(res, default=str)[:600]}")
        return 0
    if a.backup:
        b, r = backup(), rotate_logs()
        if b.get("ok"):
            s = load_state()
            s["last_backup_t"], s["last_backup_files"] = int(time.time()), b.get("files")
            save_state(s)
        print(json.dumps({"backup": b, "logs": r}, indent=1))
        return 0 if b.get("ok") else 1
    if a.restore is not None:
        r = restore(a.restore, yes=a.yes)
        print(json.dumps(r, indent=1))
        return 0 if r.get("ok") else 1
    if a.update_guard:
        code, why = update_guard()
        print(why)
        return code
    if a.wait_server is not None:
        ok = wait_server(a.wait_server)
        print("dashboard is up" if ok else "dashboard did not answer")
        return 0 if ok else 1
    if a.after_update:
        return after_update()
    if a.translate is not None:
        tr = translate(a.translate)
        print(f"{tr['what']}\n-> {tr['fix']}" if tr else "Not a known error: send it to Claude.")
        return 0
    if a.presession or a.eod or a.weekly:
        now = time.time()
        st = load_state()
        ctx = gather(now, state=st)
        checks = run_checks(ctx)
        view = account_view(ctx["hb"], now)
        p = (presession_notice(checks, view, now) if a.presession else eod_notice(view, now) if a.eod
             else weekly_notice(view, st, checks, now))
        print(f"{p['title']}\n{p['body']}")
        if a.send:
            p["key"] += f":manual:{int(now)}"
            print(json.dumps(send(p, st)))
            save_state(st)
        return 0
    ctx = gather()
    checks = run_checks(ctx)
    if a.json:
        print(json.dumps(checks, indent=1))
    else:
        print(render(checks, now=ctx["now"]))
    s = load_state()
    s["last_checks"] = {"t": int(ctx["now"]), **summary(checks)}
    save_state(s)
    return 1 if summary(checks)["bad"] else 0


if __name__ == "__main__":
    sys.exit(main())
