"""DATA PIPE (owner 2026-11-18: "the bot and you should constantly be learning ... more data, better communication").

Claude's research data stopped at Oct 16 (TradingView exports) and Nov 6 (the last heartbeat bars): the first GitHub account
was suspended, so nothing but the small ntfy status left the PC. This sends the PC's day to the cloud once a day after the
close, on the same private backup repo the PC already updates from (update_source.json: dcondax1-wq/olympus), on its own
branch `data`. docs/DATA_PIPE.md (plain words).

What one day is (days/YYYY-MM-DD/ on branch `data`; small gzip files; the CME day: 18:00 ET the evening before -> 17:00 ET):
  bars/<ROOT>_1m.csv.gz, bars/<ROOT>_5m.csv.gz   NinjaTrader bars of every LE_BarFeed / LE_Feed chart root (MNQ, NQ, MES, ES)
                                                 from le_feed\\ plus the bot's own archive data/nt_bars/ (time = bar OPEN, unix s)
  trades.jsonl.gz      every ledger row of the day (Zlarior main, each extra account, ATLAS, ATLAS v2 paper, ...), live AND
                       paper, one "src" / "bot" / "acct" / "mode" each; from data/live_state*.json + logs/exec_audit/ledger.jsonl
                       + this pipe's own archive (logs/datapipe/ledger_archive.jsonl, collected every 15 minutes, because the
                       state files keep today only)
  decisions.jsonl.gz   the Bot Brain's thought log (data/brain/<day>.jsonl: "why no trade") + the entries the bot held back
                       (logs/exec_audit/notes.json "blocked": feed stale, sizer, late, refused)
  twin.json.gz         live vs the backtest twin: engine/fill_audit's nightly verdict + rows (logs/exec_audit/nightly/<day>.json,
                       built here when missing) and engine/live_learning's trade reviews of the day
  review.json          the ZEUS daily review (engine/zeus_review.py) of that day
  proposals.jsonl      strategy ideas for Claude's research queue (never a live setting)
  manifest.json        what is in the folder: sizes, sha256, row counts, chart contract, code version
Privacy: account names become "...1234" (last 4), no balances / cash, no file paths, never the live phrase (scrub()).
Append-only: commits on top of the branch tip, never a force push, never a deleted file; a file already on the branch is only
replaced inside REPLACE_DAYS (a day packed before its close is completed later). Only the branch `data`, never `pc` / `main`.

night-data 2026-11-18: the git push below is OFF unless LE_DATAPIPE_GIT=1 (or `run --git`): the backup repo turned out PUBLIC
(the branch would publish every trade forever) and the PC has no push sign-in. The nightly run still packs + reviews locally
(logs/datapipe/days/), and Claude gets the days over ntfy on request (engine/datafeed.py; the hook is in maybe_run).

How it pushes: like the heartbeat (engine/heartbeat.py), from a PRIVATE scratch git dir (data/datapipe_pub.git, gitignored):
the project's own .git is never written (the auto-update needs a clean tree), every git call has a hard timeout, never
prompts (Git Credential Manager's saved sign-in for the backup account, the one the auto-update fetches with), plumbing only
(hash-object / update-index / write-tree / commit-tree) on a shallow fetch of the branch tip, then a plain fast-forward push.
A refused push (someone moved the branch) is rebuilt on the new tip once.

Schedule: maybe_run() from the PC's 15-minute report task (tools/pc_report.py) and the 5-minute ops task
(engine/ops_checks.tick): every call copies new ledger rows into the archive (cheap); from 17:05 ET on a weekday (any time
outside 01:50-16:00 ET when a session is missing) it starts ONE detached low-priority child that packs every day not on the
branch yet (back to BACKFILL_DAYS), runs the ZEUS review of the newest day, and pushes. Windows only (LE_DATAPIPE=1 forces it
elsewhere, LE_DATAPIPE=0 turns it off). Never trades, arms, routes or changes a setting; never raises into its caller.

    python -X utf8 -m engine.datapipe run               # now (on demand): pack + review + push the missing days
    python -X utf8 -m engine.datapipe run --day 2026-11-18 [--no-push]
    python -X utf8 -m engine.datapipe run --signin      # the same, allowing the GitHub sign-in window once
    python -X utf8 -m engine.datapipe status
Cloud side: python tools/data_pull.py (git fetch olympus data -> data/pc_days/ -> data/NQ_1m.csv ...). Tests: tests/test_datapipe.py.
"""
from __future__ import annotations

import datetime as dt
import glob
import gzip
import hashlib
import io
import json
import os
import re
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
VERSION = 1
BRANCH = "data"
_BRANCH_RE = re.compile(r"^data$")                    # this pipe only ever writes the branch `data`
SCRATCH_REL = os.path.join("data", "datapipe_pub.git")
WORK = os.path.join(ROOT, "logs", "datapipe")          # logs/ is gitignored: state, local copies, archive, log
DAYS_DIR = os.path.join(WORK, "days")                  # the same files as on the branch (the review's history on the PC)
ARCHIVE = "ledger_archive.jsonl"
BACKFILL_DAYS = 45                                     # first run: every day the NinjaTrader archive still has (1m: 40 days)
REPLACE_DAYS = 3                                       # a file of a day this recent may be replaced (packed before its close)
KEEP_LOCAL_DAYS = 120
DUE_FROM = 17 * 60 + 5                                 # ET minutes: after CME's 17:00 close (+ the 16:05 fill audit, 16:35 backup)
BLACKOUT = (110, 960)                                  # weekdays 01:50-16:00 ET: the session, no catch-up runs
MAX_TRIES = 3                                          # child starts a day before it gives up (a crash loop never spins)
STALE_LOCK_S = 3600
GIT_TIMEOUT_S = 60.0
PUSH_TIMEOUT_S = 180.0
METALS = ("GC", "MGC", "SI", "SIL")                    # COMEX gold / silver (+ micros) when NinjaTrader has a chart of them: 1-minute
                                                       # only, only around the Kalshi K8 metals windows (night-learnloop 2026-11-19)
ROOTS = ("MNQ", "NQ", "MES", "ES") + METALS
METAL_WINDOWS_ET = ((4 * 60 + 45, 5 * 60 + 45), (15 * 60 + 45, 17 * 60 + 15))   # 04:45-05:45 and 15:45-17:15 ET
METAL_WINDOW_LONDON = (9 * 60 + 45, 10 * 60 + 45)     # 09:45-10:45 London: the K8 morning leg follows London (06:15 ET Mar 15-26)
TFS = ("1m", "5m")
_COMMIT_ENV = {"GIT_AUTHOR_NAME": "olympus-pc-data", "GIT_AUTHOR_EMAIL": "pc@liquidity-engine.local",
               "GIT_COMMITTER_NAME": "olympus-pc-data", "GIT_COMMITTER_EMAIL": "pc@liquidity-engine.local"}
_MOVED = ("non-fast-forward", "fetch first", "rejected", "stale info")
README = (b"# OLYMPUS PC data (append-only)\n\nOne folder per CME day under days/YYYY-MM-DD/: NinjaTrader bars, the bots' trades "
          b"(live + paper), decisions, live vs backtest twin, the ZEUS daily review. Written by the PC (engine/datapipe.py), "
          b"read by Claude (tools/data_pull.py). Account names are cut to the last 4.\n")


# ================================================================================================ small helpers
def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def trading_day(t) -> str:
    """18:00 ET starts the next trading day (engine/live.trading_day)."""
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def prev_weekday(day: str) -> str:
    d = dt.date.fromisoformat(day) - dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d.isoformat()


def last_session(now) -> str:
    """The newest session that has closed: today from 17:05 ET on a weekday, else the weekday before."""
    e = _et(now)
    if e.weekday() < 5 and e.hour * 60 + e.minute >= DUE_FROM:
        return e.date().isoformat()
    d = e.date()
    if e.weekday() >= 5:
        return prev_weekday((d + dt.timedelta(days=1)).isoformat()) if e.weekday() == 5 else prev_weekday(d.isoformat())
    return prev_weekday(d.isoformat())


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=str)
    try:
        from .fsutil import replace as _rep
        _rep(tmp, path)
    except Exception:
        os.replace(tmp, path)


def _jl_read(path) -> list:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    try:
                        j = json.loads(ln)
                    except ValueError:
                        continue
                    if isinstance(j, dict):
                        out.append(j)
    except OSError:
        pass
    return out


def gz(data: bytes) -> bytes:
    """Deterministic gzip (mtime 0): the same content is the same git blob."""
    return gzip.compress(data, compresslevel=9, mtime=0)


def ungz(data: bytes | None) -> bytes:
    if not data:
        return b""
    return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data


def jsonl_bytes(rows) -> bytes:
    return "".join(json.dumps(r, sort_keys=True, default=str, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")


def jsonl_rows(data: bytes | None) -> list:
    out = []
    for ln in ungz(data).decode("utf-8", "replace").splitlines():
        try:
            j = json.loads(ln)
        except ValueError:
            continue
        if isinstance(j, dict):
            out.append(j)
    return out


def log(text: str, work: str | None = None):
    try:
        d = work or WORK
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "datapipe.log"), "a", encoding="utf-8") as fh:
            fh.write(f"{dt.datetime.now(ET):%Y-%m-%d %H:%M:%S} ET  {scrub_text(text)[:400]}\n")
    except Exception:
        pass


# ================================================================================================ privacy
ACCOUNT_KEYS = {"account", "acct_name", "nt_account", "accountname", "account_name", "funded_name", "eval_name", "nt_name",
                "accounts"}
TEXT_KEYS = {"error", "reason", "text", "msg", "message", "note", "notes", "why", "detail", "title", "body", "line"}
DROP_KEYS = {"balance", "cash", "cash_value", "net_liq", "netliq", "net_liquidation", "buying_power", "equity", "realized",
             "unrealized", "excess", "margin", "path", "lines", "file", "folder", "host", "computer", "email", "phone",
             "password", "token", "secret", "key_secret", "api_key", "phrase", "confirm", "topic"}
_ACCT_RX = re.compile(r"\b(?=[A-Za-z0-9_-]*\d{4})(?=[A-Za-z0-9_-]*[A-Za-z])[A-Za-z][A-Za-z0-9_-]{5,}\b")
_PATHS = re.compile(r"[A-Za-z]:[\\/][^\s;,'\"()]*|/(?:home|Users|tmp|root|mnt|var)/[^\s;,'\"()]*")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def mask(name) -> str:
    s = re.sub(r"[^A-Za-z0-9]", "", str(name or ""))
    return ("..." + s[-4:]) if s else ""


def known_names(root: str = ROOT, folder: str | None = None) -> set:
    """Account names this PC knows (data/accounts.json, the NinjaTrader allowlist, account_b.json, every state file's
    nt_account, NinjaTrader's own account list). Replaced by their last 4 anywhere they appear."""
    names: set = set()

    def walk(o, k=""):
        if isinstance(o, dict):
            for kk, v in o.items():
                walk(v, str(kk).lower())
        elif isinstance(o, list):
            for v in o:
                walk(v, k)
        elif isinstance(o, str) and (k in ACCOUNT_KEYS or k in ("name", "allow", "allowed", "nt")) and len(o) >= 5 \
                and re.search(r"\d", o) and not o.lower().startswith("sim"):
            names.add(o.strip())
    for p in [os.path.join(root, "data", n) for n in ("accounts.json", "nt_accounts_allow.json", "account_b.json", "fleet.json")] + \
            glob.glob(os.path.join(root, "data", "live_state*.json")):
        walk(_read_json(p, {}) or {})
    try:
        from .broker_balance import read as _bb_read
        from .ninjatrader import default_folder as _df
        for a in ((_bb_read(folder or _df()) or {}).get("rows") or {}):
            if len(str(a)) >= 5 and re.search(r"\d", str(a)) and not str(a).lower().startswith("sim"):
                names.add(str(a).strip())
    except Exception:
        pass
    try:
        from .ninjatrader import FEED_DIR, default_folder
        p = os.path.join(folder or default_folder(), FEED_DIR, "accounts.csv")
        with open(p, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                a = ln.split(",")[0].strip()
                if len(a) >= 5 and re.search(r"\d", a) and not a.lower().startswith("sim"):
                    names.add(a)
    except Exception:
        pass
    return {n for n in names if n}


def _phrase() -> str:
    try:
        from .tradovate import LIVE_PHRASE
        return LIVE_PHRASE or ""
    except Exception:
        return ""


def scrub_text(s, names=(), generic: bool = True) -> str:
    s = str(s or "")
    for n in sorted(names or (), key=len, reverse=True):
        if n and n in s:
            s = s.replace(n, mask(n))
    p = _phrase()
    if p and p in s:
        s = s.replace(p, "<phrase>")
    s = _PATHS.sub("<path>", s)
    s = _EMAIL.sub("<email>", s)
    if generic:
        s = _ACCT_RX.sub(lambda m: mask(m.group(0)), s)
    return s


def scrub(obj, names=(), key: str = ""):
    """The privacy pass for anything that leaves the PC: account names -> last 4, balances / paths / secrets dropped."""
    k = str(key or "").lower()
    if isinstance(obj, dict):
        out = {}
        for kk, v in obj.items():
            lk = str(kk).lower()
            if lk in DROP_KEYS:
                continue
            out[kk] = scrub(v, names, lk)
        return out
    if isinstance(obj, (list, tuple)):
        return [scrub(v, names, k) for v in obj]
    if isinstance(obj, str):
        if k in ACCOUNT_KEYS:
            return obj if obj.lower().startswith("sim") else mask(obj)
        return scrub_text(obj, names, generic=k in TEXT_KEYS)
    return obj


# ================================================================================================ the day's bars
def _feed_dir(folder: str | None = None) -> str | None:
    try:
        from .ninjatrader import FEED_DIR, default_folder
        return os.path.join(folder or default_folder(), FEED_DIR)
    except Exception:
        return None


def _load_feed(path):
    """LE_BarFeed's raw CSV (no header; time = bar open, unix s) as a tidy frame; a torn last line is dropped."""
    import pandas as pd
    from . import pcbars
    try:
        df = pd.read_csv(path, header=None, names=pcbars.COLS, usecols=range(6), on_bad_lines="skip", dtype=str, engine="python")
        with open(path, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            if fh.read(1) not in (b"\n", b"\r") and len(df):
                df = df.iloc[:-1]
        for c in pcbars.COLS:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return pcbars.tidy(df.dropna(subset=["time", "open", "high", "low", "close"]))
    except Exception:
        return pcbars.tidy(None)


def bar_frames(folder: str | None = None, archive_root: str | None = None) -> dict:
    """{(root, tf): frame} of every chart root with bars: le_feed\\<ROOT>_<tf>.csv, plus the bot's archive (data/nt_bars/NQ_*)
    under the root the bot reads (its chart: MNQ, or NQ with signal_root NQ). Feed wins on overlap."""
    import pandas as pd
    from . import pcbars
    fd = _feed_dir(folder)
    out = {}
    for root in ROOTS:
        for tf in TFS:
            p = os.path.join(fd, f"{root}_{tf}.csv") if fd else None
            if p and os.path.exists(p):
                f = _load_feed(p)
                if len(f):
                    out[(root, tf)] = f
    bot_root = None
    try:
        from .ninjatrader import NinjaTraderBars
        bot_root = NinjaTraderBars(folder=folder).root_for("NQ") if fd else None
    except Exception:
        bot_root = None
    bot_root = bot_root or ("MNQ" if not any(r == "NQ" for r, _ in out) else "NQ")
    for tf in TFS:
        a = pcbars.archive_read("NQ", tf, archive_root)
        if len(a):
            have = out.get((bot_root, tf))
            out[(bot_root, tf)] = pcbars.tidy(pd.concat([a, have]) if have is not None else a)   # tidy keeps the last = feed
    return out


def chart_contracts(folder: str | None = None) -> dict:
    fd = _feed_dir(folder)
    out = {}
    for root in ROOTS:
        try:
            with open(os.path.join(fd, f"{root}_instrument.txt"), encoding="utf-8", errors="replace") as fh:
                t = fh.read().strip().splitlines()
            if t:
                out[root] = t[0].strip()[:20]
        except Exception:
            continue
    return out


def _day_mask(frame, day):
    import numpy as np
    t = frame["time"].to_numpy()
    days = np.array([trading_day(int(x)) for x in t]) if len(t) else np.array([])
    return days == day


_LONDON = ZoneInfo("Europe/London")


def metal_minute_ok(t) -> bool:
    """A metals bar (time = bar open) inside the K8 windows: 04:45-05:45 / 15:45-17:15 ET or 09:45-10:45 London."""
    e = _et(int(t))
    m = e.hour * 60 + e.minute
    if any(a <= m < b for a, b in METAL_WINDOWS_ET):
        return True
    lo = dt.datetime.fromtimestamp(int(t), _LONDON)
    m = lo.hour * 60 + lo.minute
    return METAL_WINDOW_LONDON[0] <= m < METAL_WINDOW_LONDON[1]


def day_bars(day: str, frames: dict) -> dict:
    """{"bars/<ROOT>_<tf>.csv.gz": bytes} of one CME day (weekday sessions only). Metals: 1-minute, the K8 windows only."""
    from . import pcbars
    out = {}
    for (root, tf), f in sorted(frames.items()):
        if not len(f):
            continue
        if root in METALS and tf != "1m":
            continue
        lo = int(dt.datetime.combine(dt.date.fromisoformat(day) - dt.timedelta(days=1), dt.time(18, 0), ET).timestamp())
        sub = f[(f["time"] >= lo) & (f["time"] < lo + 23 * 3600)]
        if root in METALS and len(sub):
            sub = sub[sub["time"].map(metal_minute_ok).astype(bool)]
        if len(sub):
            out[f"bars/{root}_{tf}.csv.gz"] = pcbars.encode(sub)
    return out


def bar_days(frames: dict) -> set:
    days = set()
    for f in frames.values():
        if len(f):
            for t in f["time"].to_numpy()[::30]:
                days.add(trading_day(int(t)))
            days.add(trading_day(int(f["time"].iloc[-1])))
    return {d for d in days if dt.date.fromisoformat(d).weekday() < 5}


# ================================================================================================ trades (every ledger)
BOT_OF = (("acctb", "atlas"), ("atlas_v2", "atlas_v2"), ("acctc", "blitz"), ("acctr", "rapid"), ("fleet", "zlarior"),
          ("accounts", "zlarior"), ("lit", "zlarior"), ("si", "other"))


def _src_bot(stem: str) -> tuple:
    """data/live_state<suffix>.json -> (src, bot, acct)."""
    suf = stem[len("live_state"):].lstrip("_")
    if not suf:
        return "main", "zlarior", "zlarior"
    for k, b in BOT_OF:
        if suf == k or suf.startswith(k + "."):
            return suf, b, ("atlas" if b == "atlas" else b)
    return suf, "other", suf


def _mode(row: dict, st_adapter: str | None, account: str | None) -> str:
    res = row.get("result") if isinstance(row.get("result"), dict) else {}
    ad = str(res.get("adapter") or row.get("adapter") or st_adapter or "").lower()
    if ad in ("paper", "", "none"):
        return "paper"
    a = str(res.get("account") or row.get("account") or account or "")
    return "sim" if a.lower().startswith("sim") else "live"


def _rkey(r) -> str:
    return json.dumps([r.get("src"), r.get("t"), r.get("side"), r.get("entry_t"), r.get("stop"), r.get("reason")], default=str)


def ledger_rows(root: str = ROOT, exec_store: str | None = None) -> list:
    """Every ledger row the PC holds right now, tagged {"src", "bot", "acct", "mode"} (raw: not scrubbed yet)."""
    out = []
    for p in sorted(glob.glob(os.path.join(root, "data", "live_state*.json"))):
        stem = os.path.basename(p)[:-5]
        if ".corrupt" in stem or stem.endswith(".tmp"):
            continue
        st = _read_json(p, {}) or {}
        if not isinstance(st, dict):
            continue
        src, bot, acct = _src_bot(stem)
        if isinstance(st.get("ledger"), list):
            for r in st["ledger"]:
                if isinstance(r, dict) and r.get("t") is not None:
                    out.append({**r, "src": src, "bot": bot, "acct": acct, "mode": _mode(r, st.get("adapter"), st.get("nt_account"))})
        for aid, blob in ((st.get("accounts") or {}).items() if isinstance(st.get("accounts"), dict) else ()):
            for r in (blob or {}).get("ledger") or []:
                if isinstance(r, dict) and r.get("t") is not None:
                    out.append({**r, "src": f"accounts/{aid}", "bot": bot if bot != "other" else "zlarior", "acct": str(aid),
                                "mode": _mode(r, None, (blob or {}).get("nt_account"))})
    ep = os.path.join(exec_store or os.path.join(root, "logs", "exec_audit"), "ledger.jsonl")
    for r in _jl_read(ep):
        if r.get("t") is not None:
            out.append({**r, "src": "main", "bot": "zlarior", "acct": "zlarior", "mode": _mode(r, r.get("adapter"), None)})
    return out


KEYS = ARCHIVE + ".keys"                               # one short hash of _rkey per archived row (collect's index)
KEYS_META = ARCHIVE + ".keys.json"                     # {"size": the archive's byte size the index matches}


def _hkey(r) -> str:
    return hashlib.sha1(_rkey(r).encode("utf-8")).hexdigest()[:20]


def _archive_keys(w: str, p: str) -> set:
    """The archive's row keys: the index when it matches the archive's size, else rebuilt from the archive (and saved)."""
    try:
        size = os.path.getsize(p)
    except OSError:
        size = 0
    meta = _read_json(os.path.join(w, KEYS_META), {}) or {}
    if isinstance(meta, dict) and meta.get("size") == size:
        try:
            with open(os.path.join(w, KEYS), encoding="ascii") as fh:
                have = {ln.strip() for ln in fh if ln.strip()}
            if len(have) == int(meta.get("n") or 0):
                return have
        except (OSError, UnicodeDecodeError, ValueError):
            pass
    have = {_hkey(r) for r in _jl_read(p)}
    if size or have:
        os.makedirs(w, exist_ok=True)
        with open(os.path.join(w, KEYS), "w", encoding="ascii") as fh:
            fh.write("".join(k + "\n" for k in sorted(have)))
        _write_json(os.path.join(w, KEYS_META), {"size": size, "n": len(have)})
    return have


def collect(root: str = ROOT, work: str | None = None, exec_store: str | None = None) -> dict:
    """Copy every ledger row not seen yet into logs/datapipe/ledger_archive.jsonl (the state files keep today only). Cheap;
    called every 5-15 minutes. Never raises. The rows already archived are known from a small index (KEYS, matched to the
    archive's size by KEYS_META; rebuilt from the archive whenever they disagree), not by re-reading and re-keying the whole
    archive every tick (night-learnloop 2026-11-19: ~220 ms a tick on six months of rows; the same rows are added)."""
    try:
        w = work or WORK
        p = os.path.join(w, ARCHIVE)
        have = _archive_keys(w, p)
        new, keys = [], []
        for r in ledger_rows(root, exec_store):
            k = _hkey(r)
            if k not in have:
                have.add(k)
                new.append(r)
                keys.append(k)
        if new:
            os.makedirs(w, exist_ok=True)
            with open(p, "a", encoding="utf-8") as fh:
                for r in new:
                    fh.write(json.dumps(r, default=str) + "\n")
            with open(os.path.join(w, KEYS), "a", encoding="ascii") as fh:
                fh.write("".join(k + "\n" for k in keys))
            _write_json(os.path.join(w, KEYS_META), {"size": os.path.getsize(p), "n": len(have)})
        return {"added": len(new)}
    except Exception as e:
        return {"added": 0, "error": f"{e.__class__.__name__}"}


def day_trades(day: str, rows: list, names=()) -> list:
    """The day's ledger rows (entry_t's day, else the row time's day), de-duplicated, sorted, scrubbed."""
    seen, out = set(), []
    for r in rows:
        t = r.get("entry_t") or r.get("t")
        try:
            d = trading_day(int(t))
        except (TypeError, ValueError):
            continue
        if d != day:
            continue
        k = _rkey(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(scrub(r, names))
    return sorted(out, key=lambda r: (int(r.get("t") or 0), str(r.get("src"))))


# ================================================================================================ decisions + twin
def day_decisions(day: str, root: str = ROOT, exec_store: str | None = None, names=()) -> list:
    out = []
    for r in _jl_read(os.path.join(root, "data", "brain", f"{day}.jsonl")):
        out.append({"src": "brain", **r})
    N = _read_json(os.path.join(exec_store or os.path.join(root, "logs", "exec_audit"), "notes.json"), {}) or {}
    for k, v in sorted((N.get("blocked") or {}).items()):
        try:
            if trading_day(int(k)) == day:
                out.append({"src": "held_back", "entry_t": int(k), **(v if isinstance(v, dict) else {"reason": str(v)})})
        except (TypeError, ValueError):
            continue
    return [scrub(r, names) for r in out]


def day_twin(day: str, root: str = ROOT, exec_store: str | None = None, learn_store: str | None = None, names=(),
             build: bool = True) -> dict:
    """fill_audit's nightly verdict + rows of the day (built when missing and build=True) + live_learning's reviews."""
    es = exec_store or os.path.join(root, "logs", "exec_audit")
    nightly = _read_json(os.path.join(es, "nightly", f"{day}.json"), None)
    if nightly is None and build:
        try:
            from . import fill_audit
            nightly = fill_audit.nightly(day, store=exec_store, push_it=False, write=True)
        except Exception as e:
            nightly = {"day": day, "verdict": "not built", "text": f"twin replay failed: {e.__class__.__name__}"}
    ls = learn_store or os.path.join(root, "logs", "learning")
    reviews = []
    for r in _jl_read(os.path.join(ls, "reviews.jsonl")):
        d = r.get("day") or ((r.get("live") or {}).get("day")) or ((r.get("twin") or {}).get("day"))
        if d is None and r.get("entry_t"):
            d = trading_day(r["entry_t"])
        if d == day:
            reviews.append(r)
    return scrub({"day": day, "nightly": nightly, "reviews": reviews}, names)


# ================================================================================================ one day's folder
def _code_version(root: str = ROOT) -> str | None:
    try:
        from .heartbeat import run_cmd
        from .generated_files import git_exe
        r = run_cmd([git_exe(), "rev-parse", "--short", "HEAD"], cwd=root, timeout=20)
        return r.out.strip()[:12] if not r.returncode else None
    except Exception:
        return None


def pack_day(day: str, frames: dict, rows: list, names=(), root: str = ROOT, exec_store: str | None = None,
             learn_store: str | None = None, now=None, build_twin: bool = True, contracts: dict | None = None) -> dict:
    """{relative path inside days/<day>/: bytes} (manifest.json last). review.json / proposals.jsonl are added by run()."""
    now = int(now if now is not None else time.time())
    files = dict(day_bars(day, frames))
    tr = day_trades(day, rows, names)
    files["trades.jsonl.gz"] = gz(jsonl_bytes(tr))
    dc = day_decisions(day, root, exec_store, names)
    files["decisions.jsonl.gz"] = gz(jsonl_bytes(dc))
    tw = day_twin(day, root, exec_store, learn_store, names, build=build_twin)
    files["twin.json.gz"] = gz(json.dumps(tw, sort_keys=True, default=str).encode("utf-8"))
    close = int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(17, 0), ET).timestamp())
    files["manifest.json"] = manifest(day, files, now, partial=now < close, contracts=contracts,
                                      counts={"trades": len(tr), "decisions": len(dc),
                                              "entries": sum(1 for r in tr if r.get("side") in ("buy", "sell")),
                                              "twin_rows": len(((tw.get("nightly") or {}).get("rows")) or []),
                                              "reviews": len(tw.get("reviews") or [])}, root=root)
    return files


def manifest(day, files: dict, now, partial=False, contracts=None, counts=None, root: str = ROOT) -> bytes:
    from . import pcbars
    info = {}
    for p, b in sorted(files.items()):
        if p == "manifest.json":
            continue
        x = {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        if p.startswith("bars/"):
            f = pcbars.decode(b)
            x.update(rows=int(len(f)), first=int(f["time"].min()) if len(f) else None, last=int(f["time"].max()) if len(f) else None)
        info[p] = x
    m = {"v": VERSION, "day": day, "made_t": int(now), "partial": bool(partial), "files": info, "counts": counts or {},
         "chart": contracts or {}, "code": _code_version(root), "privacy": "account names cut to the last 4; no balances"}
    return json.dumps(m, indent=1, sort_keys=True).encode("utf-8")


def write_local(day: str, files: dict, days_dir: str | None = None):
    d = os.path.join(days_dir or DAYS_DIR, day)
    for p, b in files.items():
        fp = os.path.join(d, *p.split("/"))
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "wb") as fh:
            fh.write(b)


def prune_local(days_dir: str | None = None, now=None, keep: int = KEEP_LOCAL_DAYS):
    import shutil
    base = days_dir or DAYS_DIR
    cut = (dt.date.fromtimestamp(int(now or time.time())) - dt.timedelta(days=keep)).isoformat()
    for d in glob.glob(os.path.join(base, "????-??-??")):
        if os.path.basename(d) < cut:
            shutil.rmtree(d, ignore_errors=True)


def load_day(path: str) -> dict:
    """A day folder (PC local copy, or the cloud's data/pc_days/<day>/) as the review's bundle."""
    def rb(name):
        try:
            with open(os.path.join(path, *name.split("/")), "rb") as fh:
                return fh.read()
        except OSError:
            return None
    man = json.loads(rb("manifest.json") or b"{}")
    try:
        twin = json.loads(ungz(rb("twin.json.gz")) or b"{}")
    except ValueError:
        twin = {}
    try:
        review = json.loads(rb("review.json") or b"null")
    except ValueError:
        review = None
    return {"day": man.get("day") or os.path.basename(path.rstrip("/\\")), "manifest": man,
            "trades": jsonl_rows(rb("trades.jsonl.gz")), "decisions": jsonl_rows(rb("decisions.jsonl.gz")), "twin": twin,
            "review": review, "proposals": jsonl_rows(rb("proposals.jsonl"))}


def load_days(days_dir: str, upto: str | None = None, n: int = 60) -> list:
    ds = sorted(os.path.basename(d) for d in glob.glob(os.path.join(days_dir, "????-??-??")) if os.path.isdir(d))
    if upto:
        ds = [d for d in ds if d <= upto]
    return [load_day(os.path.join(days_dir, d)) for d in ds[-n:]]


# ================================================================================================ git: the push
def _git_env(interactive: bool = False, extra: dict | None = None) -> dict:
    env = {**os.environ, **(extra or {})}
    if interactive:
        env.pop("GIT_TERMINAL_PROMPT", None)
        env.pop("GCM_INTERACTIVE", None)
    else:
        env.update({"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"})
    return env


def _net(interactive: bool = False) -> list:
    return ["-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=30", "-c", "push.negotiate=false",
            "-c", f"credential.interactive={'auto' if interactive else 'never'}"]


class Git:
    """The git layer (swappable in tests): run(args, inp=None, env=None, timeout) -> (code, out, err)."""

    def __init__(self, git_dir: str, cwd: str = ROOT, exe: str | None = None):
        self.git_dir, self.cwd = git_dir, cwd
        if exe is None:
            try:
                from .generated_files import git_exe
                exe = git_exe()
            except Exception:
                exe = "git"
        self.exe = exe

    def run(self, args, inp: bytes | None = None, env=None, timeout: float = GIT_TIMEOUT_S, bare: bool = True):
        from .heartbeat import run_cmd
        cmd = [self.exe, *(["--git-dir", self.git_dir] if bare else []), *args]
        r = run_cmd(cmd, cwd=self.cwd, inp=inp, timeout=timeout, env=env or _git_env())
        return r.returncode, (r.stdout or b"").decode("utf-8", "replace").strip(), (r.stderr or b"").decode("utf-8", "replace").strip()


def _redact(s: str) -> str:
    return re.sub(r"(https?://)[^@\s/]+@", r"\1", s or "")[-300:]


def ensure_scratch(g: Git) -> str | None:
    """The private bare repo, with this repo's local credential / http / url settings (as the heartbeat's). Error or None."""
    try:
        if not os.path.isdir(os.path.join(g.git_dir, "objects")):
            os.makedirs(os.path.dirname(g.git_dir), exist_ok=True)
            c, _o, e = g.run(["init", "-q", "--bare", g.git_dir], bare=False)
            if c:
                return "git init failed: " + _redact(e)
            c, o, _e = g.run(["config", "--local", "--get-regexp", r"^(credential\..*|core\.sshcommand|http\..*|url\..*)$"],
                             bare=False)
            for ln in (o.splitlines() if c == 0 else []):
                k, _, v = ln.partition(" ")
                if k and v:
                    g.run(["config", "--add", k, v])
        try:
            from .heartbeat import _clear_stale_locks
            _clear_stale_locks(g.git_dir)
        except Exception:
            pass
        return None
    except Exception as e:
        return f"{e.__class__.__name__}: {e}"


def remote_tip(g: Git, url: str, branch: str = BRANCH, interactive: bool = False) -> tuple:
    c, o, e = g.run([*_net(interactive), "ls-remote", url, f"refs/heads/{branch}"], env=_git_env(interactive),
                    timeout=900 if interactive else GIT_TIMEOUT_S)      # --signin: time to finish the GitHub window
    if c:
        return None, _redact(e) or "ls-remote failed"
    for ln in o.splitlines():
        sha, _, ref = ln.partition("\t")
        if ref.strip() == f"refs/heads/{branch}" and re.fullmatch(r"[0-9a-f]{40,64}", sha.strip()):
            return sha.strip(), None
    return "", None


def tree_of(g: Git, rev: str, prefix: str = "") -> dict:
    """{path: blob} of rev (under prefix)."""
    c, o, _e = g.run(["ls-tree", "-r", rev, *([prefix] if prefix else [])])
    out = {}
    for ln in (o.splitlines() if c == 0 else []):
        meta, _, path = ln.partition("\t")
        parts = meta.split()
        if len(parts) >= 3 and parts[1] == "blob":
            out[path] = parts[2]
    return out


def show(g: Git, rev: str, path: str) -> bytes | None:
    from .heartbeat import run_cmd
    r = run_cmd([g.exe, "--git-dir", g.git_dir, "show", f"{rev}:{path}"], cwd=g.cwd, timeout=GIT_TIMEOUT_S, env=_git_env())
    return r.stdout if not r.returncode else None


def fetch_tip(g: Git, url: str, tip: str, branch: str = BRANCH, interactive: bool = False) -> str | None:
    """Shallow fetch of the branch tip into the scratch dir. Error or None."""
    if not tip:
        return None
    c, _o, e = g.run([*_net(interactive), "fetch", "-q", "--depth", "1", "--no-tags", url,
                      f"+refs/heads/{branch}:refs/dp/tip"], env=_git_env(interactive), timeout=PUSH_TIMEOUT_S)
    return (_redact(e) or "fetch failed") if c else None


def push_files(files: dict, url: str, git_dir: str | None = None, branch: str = BRANCH, replace_ok=None, g: Git | None = None,
               interactive: bool = False, message: str = "pc data") -> dict:
    """Add `files` ({branch path: bytes}) on top of the branch tip and push it (never forced). replace_ok(path) -> bool for a
    path already on the branch with other content (False = keep the branch's copy). Returns {"ok", "commit" | "error",
    "added", "replaced", "kept", "unchanged"}. Never raises."""
    t0 = time.monotonic()
    try:
        if not _BRANCH_RE.match(str(branch or "")):
            return {"ok": False, "error": f"refused: the data pipe only writes the branch '{BRANCH}', never '{branch}'"}
        if not url:
            return {"ok": False, "error": "no backup repo (update_source.json)"}
        g = g or Git(git_dir or os.path.join(ROOT, SCRATCH_REL))
        err = ensure_scratch(g)
        if err:
            return {"ok": False, "error": err}
        res: dict = {}
        for attempt in (1, 2):
            tip, terr = remote_tip(g, url, branch, interactive)
            if tip is None:
                return {"ok": False, "error": f"backup repo not reachable: {terr}", "attempts": attempt}
            ferr = fetch_tip(g, url, tip, branch, interactive)
            if ferr:
                return {"ok": False, "error": ferr, "attempts": attempt}
            have = tree_of(g, tip) if tip else {}
            idx = os.path.join(g.git_dir, "dp_index")
            ienv = _git_env(False, {"GIT_INDEX_FILE": idx})
            try:
                os.remove(idx)
            except OSError:
                pass
            c, _o, e = g.run(["read-tree", tip] if tip else ["read-tree", "--empty"], env=ienv)
            if c:
                return {"ok": False, "error": "read-tree failed: " + _redact(e)}
            added = replaced = kept = 0
            todo = dict(files)
            if "README.md" not in have and "README.md" not in todo:
                todo["README.md"] = README
            for path, data in sorted(todo.items()):
                if not data or path.startswith("/") or ".." in path.split("/") or "\\" in path or "\n" in path:
                    continue
                c, blob, e = g.run(["hash-object", "-w", "--stdin"], inp=bytes(data))
                if c or len(blob) < 40:
                    return {"ok": False, "error": "hash-object failed: " + _redact(e)}
                old = have.get(path)
                if old == blob:
                    continue
                if old is not None and not (replace_ok or (lambda p: False))(path):
                    kept += 1
                    continue
                c, _o, e = g.run(["update-index", "--add", "--cacheinfo", f"100644,{blob},{path}"], env=ienv)
                if c:
                    return {"ok": False, "error": "update-index failed: " + _redact(e)}
                replaced, added = (replaced + 1, added) if old is not None else (replaced, added + 1)
            c, tree, e = g.run(["write-tree"], env=ienv)
            if c or not tree:
                return {"ok": False, "error": "write-tree failed: " + _redact(e)}
            if tip:
                c, ttree, _e = g.run(["rev-parse", f"{tip}^{{tree}}"])
                if c == 0 and ttree == tree:
                    return {"ok": True, "unchanged": True, "commit": tip[:10], "added": 0, "replaced": 0, "kept": kept,
                            "took_ms": int((time.monotonic() - t0) * 1000)}
            c, commit, e = g.run(["-c", "commit.gpgsign=false", "commit-tree", tree, *(["-p", tip] if tip else []), "-m", message],
                                 env=_git_env(False, _COMMIT_ENV))
            if c or not commit:
                return {"ok": False, "error": "commit-tree failed: " + _redact(e)}
            c, _o, e = g.run([*_net(interactive), "push", "-q", url, f"{commit}:refs/heads/{branch}"], env=_git_env(interactive),
                             timeout=PUSH_TIMEOUT_S)
            if c == 0:
                g.run(["update-ref", "refs/dp/last", commit])
                return {"ok": True, "commit": commit[:10], "added": added, "replaced": replaced, "kept": kept,
                        "attempts": attempt, "took_ms": int((time.monotonic() - t0) * 1000)}
            res = {"ok": False, "error": _redact(e) or "push failed", "attempts": attempt}
            if not any(m in (e or "") for m in _MOVED):
                return res
        return res
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def git_enabled(env=None) -> bool:
    """The git push to branch `data` is OFF unless LE_DATAPIPE_GIT=1 (night-data 2026-11-18): the backup repo is PUBLIC, so
    the branch would publish every trade forever, and the PC has no push sign-in (it reads the public repo anonymously). The
    data reaches Claude over ntfy on request instead (engine/datafeed.py). Off = no GitHub call at all from the pipe."""
    e = os.environ if env is None else env
    return str(e.get("LE_DATAPIPE_GIT", "")).strip() == "1"


def backup_url(root: str = ROOT, env=None) -> str | None:
    """The backup repo the PC updates from (update_source.json via engine/autoupdate.source); None = not set."""
    try:
        from .autoupdate import source
        s = source(root, env)
        return s.get("url") if s.get("remote") not in (None, "", "origin") else None
    except Exception:
        return None


# ================================================================================================ the nightly run
def branch_days(g: Git, url: str, interactive: bool = False) -> tuple:
    """({day: partial?} on the branch, error). Reads the recent days' manifests only."""
    tip, err = remote_tip(g, url, BRANCH, interactive)
    if tip is None:
        return None, err
    if not tip:
        return {}, None
    ferr = fetch_tip(g, url, tip, BRANCH, interactive)
    if ferr:
        return None, ferr
    days = {}
    for p in tree_of(g, tip, "days/"):
        m = re.match(r"days/(\d{4}-\d{2}-\d{2})/manifest\.json$", p)
        if m:
            days[m.group(1)] = None
    for d in sorted(days)[-REPLACE_DAYS - 2:]:
        try:
            days[d] = bool(json.loads(show(g, tip, f"days/{d}/manifest.json") or b"{}").get("partial"))
        except ValueError:
            days[d] = None
    return days, None


def replace_ok_for(today: str):
    lim = (dt.date.fromisoformat(today) - dt.timedelta(days=REPLACE_DAYS)).isoformat()

    def ok(path: str) -> bool:
        m = re.match(r"days/(\d{4}-\d{2}-\d{2})/", path)
        return bool(m) and m.group(1) >= lim
    return ok


def run(days=None, push: bool = True, now=None, root: str = ROOT, work: str | None = None, folder: str | None = None,
        url: str | None = None, g: Git | None = None, interactive: bool = False, review: bool = True, notify=None,
        emit=None, build_twin: bool = True, backfill: int = BACKFILL_DAYS, exec_store: str | None = None,
        learn_store: str | None = None, archive_root: str | None = None, edge: dict | None = None,
        git: bool | None = None, learn: bool | None = None, learn_notify=None) -> dict:
    """Pack the days not on the branch yet (or `days`), run the ZEUS review of the newest, then ZEUS learned (engine/zeus_learn:
    the nightly per-strategy scorecard + ONE phone line; learn=None = only on the real run, work None), push. Returns a summary.
    The push needs git=True, LE_DATAPIPE_GIT=1 or an explicit url (tests); otherwise it packs locally only (git_enabled)."""
    now = int(now if now is not None else time.time())
    w = work or WORK
    days_dir = os.path.join(w, "days")
    st = _read_json(os.path.join(w, "state.json"), {}) or {}
    out = {"t": now, "days": [], "pushed": None, "review": None, "errors": []}
    collect(root, w, exec_store)
    git_off = url is None and not (git if git is not None else git_enabled())
    if git_off:
        st["fails"] = 0                       # no push tried: the review must not say "the PC could not send its data"
        out["note"] = "git push off: the data goes to Claude over ntfy on request (engine/datafeed.py)"
    url = url if url is not None else (None if git_off else backup_url(root))
    g = g or Git(os.path.join(root, SCRATCH_REL), cwd=root)
    on_branch = {}
    if push and url:
        if ensure_scratch(g) is None:
            ob, err = branch_days(g, url, interactive)
            if ob is None:
                out["errors"].append(f"branch not readable: {err}")
            else:
                on_branch = ob
    frames = bar_frames(folder, archive_root)
    rows = _jl_read(os.path.join(w, ARCHIVE)) + ledger_rows(root, exec_store)
    names = known_names(root, folder)
    newest = last_session(now)
    if days:
        todo = sorted(set(days))
    else:
        lo = (dt.date.fromisoformat(newest) - dt.timedelta(days=backfill)).isoformat()
        cand = {d for d in bar_days(frames) if lo <= d <= newest}
        for r in rows:
            try:
                d = trading_day(int(r.get("entry_t") or r.get("t")))
            except (TypeError, ValueError):
                continue
            if lo <= d <= newest and dt.date.fromisoformat(d).weekday() < 5:
                cand.add(d)
        local = {os.path.basename(p) for p in glob.glob(os.path.join(days_dir, "????-??-??"))}
        done = set(on_branch) if (push and url) else local
        partial = {d for d, p in on_branch.items() if p} | {d for d in (st.get("partial") or [])}
        todo = sorted(d for d in cand if d not in done or d in partial or d == newest and d not in local)
    contracts = chart_contracts(folder)
    packed = {}
    for d in todo:
        try:
            packed[d] = pack_day(d, frames, rows, names, root, exec_store, learn_store, now, build_twin=build_twin and d >= prev_weekday(newest),
                                 contracts=contracts)
            write_local(d, packed[d], days_dir)
            out["days"].append(d)
        except Exception as e:
            out["errors"].append(f"{d}: {e.__class__.__name__}: {str(e)[:120]}")
    rv_day = max(packed) if packed else None
    rv = None
    if review and rv_day:
        try:
            from . import zeus_review
            R = zeus_review.nightly(rv_day, days_dir=days_dir, out_dir=zeus_review.OUT if work is None else os.path.join(w, "zeus"),
                                    now=now, notify=notify, emit=emit, push_state=st, edge=edge)
            extra = {"review.json": json.dumps(R["review"], indent=1, sort_keys=True, default=str).encode("utf-8")}
            if R["review"].get("proposals"):
                extra["proposals.jsonl"] = jsonl_bytes(R["review"]["proposals"])
            packed[rv_day].update(extra)
            write_local(rv_day, extra, days_dir)
            out["review"] = {k: R["review"].get(k) for k in ("day", "text", "action", "light")}
            rv = R["review"]
        except Exception as e:
            out["errors"].append(f"review: {e.__class__.__name__}: {str(e)[:160]}")
    if rv_day and (learn if learn is not None else work is None) and str(os.environ.get("LE_LEARNED", "")).strip() != "0":
        try:                                  # Kalshi K8 weekly self-check (engine/kalshi_adapt.py): only ever shrinks / pauses a leg
            if work is None:                  # the real nightly child only (tests pass their own work dir: no network, no PC files)
                from . import kalshi_adapt
                out["kadapt"] = (kalshi_adapt.pc_weekly(root=root, now=now) or {}).get("line")
        except Exception:  # noqa: BLE001
            pass
        try:                                  # ZEUS learned (engine/zeus_learn.py): the nightly scorecard, research + advice only
            from . import zeus_learn
            L = zeus_learn.nightly(rv_day, days_dir, out_dir=zeus_learn.OUT if work is None else os.path.join(w, "learn"), now=now,
                                   notify=learn_notify, review=rv, root=root)
            packed[rv_day]["learn.json"] = json.dumps(L["public"], indent=1, sort_keys=True, default=str).encode("utf-8")
            out["learned"] = L["learned"]["line"]
        except Exception as e:
            out["errors"].append(f"learned: {e.__class__.__name__}: {str(e)[:160]}")
    if push and url and packed:
        files = {f"days/{d}/{p}": b for d, fs in packed.items() for p, b in fs.items()}
        res = push_files(files, url, g=g, replace_ok=replace_ok_for(newest), interactive=interactive,
                         message=f"pc data {min(packed)}..{max(packed)} ({len(packed)} day{'s' if len(packed) != 1 else ''})")
        out["pushed"] = {k: v for k, v in res.items() if k != "took_ms"}
        if res.get("ok"):
            st["fails"] = 0
            st["last_push"] = {"t": now, "days": sorted(packed), "commit": res.get("commit")}
        else:
            st["fails"] = int(st.get("fails") or 0) + 1
            st["last_error"] = {"t": now, "error": scrub_text(res.get("error"), names)[:200]}
    elif push and not url and not git_off:
        out["errors"].append("no backup repo set (update_source.json): packed locally only")
    st["partial"] = sorted(d for d, fs in packed.items() if json.loads(fs["manifest.json"]).get("partial"))
    st["last_run"] = {"t": now, "days": sorted(packed), "errors": out["errors"][:5]}
    st["done_day"] = newest if (not push or not url or (out["pushed"] or {}).get("ok") or not packed) else st.get("done_day")
    _write_json(os.path.join(w, "state.json"), st)
    prune_local(days_dir, now)
    log(f"run: days {out['days'][:3]}{'...' if len(out['days']) > 3 else ''} ({len(out['days'])}) pushed "
        f"{(out['pushed'] or {}).get('ok')} {(out['pushed'] or {}).get('error') or ''} errors {out['errors'][:2]}", w)
    return out


# ================================================================================================ the schedule
def due(now, st: dict) -> tuple:
    """(ok, why): after 17:05 ET on a weekday for today's session; outside 01:50-16:00 ET for a missed one."""
    e = _et(now)
    mod = e.hour * 60 + e.minute
    newest = last_session(now)
    if st.get("done_day") and st["done_day"] >= newest:
        return False, "done for the newest session"
    if e.weekday() < 5 and BLACKOUT[0] <= mod < BLACKOUT[1]:
        return False, "session hours"
    tries = (st.get("tries") or {}).get(newest, 0)
    if tries >= MAX_TRIES:
        return False, f"started {MAX_TRIES} times for {newest}"
    return True, newest


def _pid_alive(pid) -> bool:
    try:
        from .learn_loop import _pid_alive as _a
        return _a(pid)
    except Exception:
        return False


def spawn(work: str | None = None) -> int | None:
    """One detached, low-priority child with no window (it outlives the 15-minute task)."""
    try:
        import subprocess
        w = work or WORK
        os.makedirs(w, exist_ok=True)
        lg = open(os.path.join(w, "child.log"), "a", encoding="utf-8")
        cmd = [sys.executable, "-X", "utf8", "-m", "engine.datapipe", "run", "--from-hook", "--quiet"]
        env = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "PYTHONIOENCODING": "utf-8",
               "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
        kw = {"cwd": ROOT, "stdout": lg, "stderr": lg, "stdin": subprocess.DEVNULL, "env": env}
        if os.name == "nt":
            base = 0x00004000 | 0x08000000 | 0x00000200          # BELOW_NORMAL | CREATE_NO_WINDOW | NEW_PROCESS_GROUP
            try:
                return subprocess.Popen(cmd, creationflags=base | 0x01000000, **kw).pid
            except OSError:
                return subprocess.Popen(cmd, creationflags=base, **kw).pid
        kw["start_new_session"] = True
        kw["preexec_fn"] = lambda: os.nice(10)
        return subprocess.Popen(cmd, **kw).pid
    except Exception:
        return None


def maybe_run(now=None, say=print, env=None, work: str | None = None, spawn_fn=None, root: str = ROOT, feed=None) -> int | None:
    """The PC tasks' hook (engine/ops_checks.tick every 5 min): collect the ledgers, answer a data request of Claude's over
    ntfy (engine/datafeed.maybe_answer, or `feed` in tests), then start the nightly child once when due. Never raises."""
    try:
        e = os.environ if env is None else env
        sw = str(e.get("LE_DATAPIPE", "")).strip()
        if sw == "0" or (e.get("LE_PR_NO_NET") == "1" and spawn_fn is None):
            return None
        if os.name != "nt" and sw != "1":
            return None
        w = work or WORK
        collect(root, w)
        now = int(now if now is not None else time.time())
        if feed is not None or work is None:  # Claude's data requests over ntfy (engine/datafeed.py): one GET, outside the session
            try:
                if feed is None:
                    from .datafeed import maybe_answer as feed
                feed(now=now, env=e, say=say)
            except Exception:
                pass
        st = _read_json(os.path.join(w, "state.json"), {}) or {}
        ok, day = due(now, st)
        if not ok:
            return None
        lk = _read_json(os.path.join(w, "running.json"), None)
        if isinstance(lk, dict) and now - int(lk.get("t") or 0) < STALE_LOCK_S and _pid_alive(lk.get("pid")):
            return None
        pid = (spawn_fn or spawn)(w)
        if pid:
            _write_json(os.path.join(w, "running.json"), {"pid": pid, "t": now})
            st["tries"] = {day: int((st.get("tries") or {}).get(day, 0)) + 1}
            _write_json(os.path.join(w, "state.json"), st)
            say(f"  [OK]  data pipe started for {day} (bars + trades -> backup repo branch data; pid {pid})")
        return pid
    except Exception as ex:  # noqa: BLE001
        say(f"  [..] data pipe skipped: {ex.__class__.__name__}: {str(ex)[:120]}")
        return None


def status(work: str | None = None) -> dict:
    w = work or WORK
    st = _read_json(os.path.join(w, "state.json"), {}) or {}
    local = sorted(os.path.basename(p) for p in glob.glob(os.path.join(w, "days", "????-??-??")))
    return {"done_day": st.get("done_day"), "last_push": st.get("last_push"), "fails": st.get("fails", 0),
            "last_error": st.get("last_error"), "last_run": st.get("last_run"), "local_days": len(local),
            "newest_local": local[-1] if local else None, "backup": bool(backup_url())}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.datapipe", description="PC -> backup repo branch data (bars, trades, review)")
    ap.add_argument("cmd", choices=("run", "status", "collect"), nargs="?", default="status")
    ap.add_argument("--day", action="append", help="pack this day (YYYY-MM-DD); repeatable")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--no-review", action="store_true")
    ap.add_argument("--signin", action="store_true", help="allow the GitHub sign-in window (Git Credential Manager) once")
    ap.add_argument("--git", action="store_true", help="push to the backup's branch data this time (off by default: git_enabled)")
    ap.add_argument("--backfill", type=int, default=BACKFILL_DAYS)
    ap.add_argument("--from-hook", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        print(json.dumps(status(), indent=1, default=str))
        return 0
    if a.cmd == "collect":
        print(json.dumps(collect()))
        return 0
    try:
        from .learn_loop import lower_priority
        lower_priority()
    except Exception:
        pass
    try:
        r = run(days=a.day, push=not a.no_push, interactive=a.signin, review=not a.no_review, backfill=a.backfill,
                git=True if a.git else None)
    finally:
        if a.from_hook:
            try:
                os.remove(os.path.join(WORK, "running.json"))
            except OSError:
                pass
    if not a.quiet:
        p = r.get("pushed") or {}
        print(f"days packed: {len(r['days'])} ({', '.join(r['days'][-5:])}{' ...' if len(r['days']) > 5 else ''})")
        print("pushed: " + ("yes " + str(p.get("commit")) + (" (no change)" if p.get("unchanged") else "") if p.get("ok") else
                            f"NO ({p.get('error')})" if p else "no (nothing to push / --no-push)"))
        if r.get("note"):
            print("  " + r["note"] + (": --signin is not needed" if a.signin else ""))
        if r.get("review"):
            print(r["review"].get("text"))
        for e in r["errors"]:
            print("  [..]", e)
    return 0 if not r["errors"] or (r.get("pushed") or {}).get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
