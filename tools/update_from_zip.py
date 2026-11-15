#!/usr/bin/env python3
"""Update the bot folder from a code zip, without GitHub (owner 2026-11-11: the account is gone, `git pull` no longer works).

The zip is the output of tools/make_backup.py (OLYMPUS_BACKUP_<date>_<commit>.zip + its .sha256.txt). The owner downloads both to
the PC and double-clicks UPDATE_FROM_ZIP.bat; UNDO_UPDATE.bat puts the old files back.

    python tools/update_from_zip.py                      newest OLYMPUS_BACKUP_*.zip in the bot folder, Downloads or Desktop
    python tools/update_from_zip.py C:\\path\\code.zip      this zip
    python tools/update_from_zip.py --dry-run            say what would change, change nothing
    python tools/update_from_zip.py --undo               put back what the last update replaced, remove what it added
    python tools/update_from_zip.py --force              also while the bot is running or the market is open (not advised)
    python tools/update_from_zip.py --allow-market-open  the bot is stopped, the market is open, go on (the .bat asks first)
    python tools/update_from_zip.py --check              read only, no guards (SETUP_EVERYTHING.bat step 1): is an update due?
    --folder DIR   the bot folder (default: the folder this script is in)      --port N   the bot server's port (default 8766)

What it guarantees:
  - REFUSES while the bot is running (its server answers on the port) or while the futures market is open, unless forced.
  - VERIFIES the zip: it opens, every file's checksum is right, it is this project, and its SHA-256 equals the line in the
    .sha256.txt next to it when that file is there. A wrong SHA-256 is never forced.
  - NEVER overwrites a local-only file: the hard list below (alerts, TradingView, autostart, bot state, memory, .env, NinjaTrader
    bars, logs, backups) and anything the folder's or the zip's .gitignore names. A hard-list path is never written at all.
  - A root live_model*.json whose VALUES differ from the zip's (2026-11-14, 3-way): nothing on the PC writes these files (only the
    repo does), so a copy that is byte for byte one of the REPO'S OWN older versions (its SHA-256, UTF-8 BOM and line ends aside, is
    in tools/model_versions.json: the zip's copy, else the folder's own; tools/model_versions.py builds it from git) is REPLACED
    with the zip's values and the summary says "updated to the new values (yours was an older version)". Any other content is
    the owner's own values: KEPT, and the summary says so. With no list in the zip or the folder every differing copy is kept.
  - The zip ALREADY IN (this very zip is the folder's last update, not undone): only the live_model*.json that update kept are
    looked at again (an older updater kept every differing one); every other file stays as it is now (later fixes are kept).
  - NEVER deletes a file, never starts / stops / arms the bot, never touches NinjaTrader, never needs the network.
  - BACKS UP first: backups/update_from_zip/<stamp>/ holds the folder's state list (state_before.txt), a copy of every file
    it replaces and a manifest; a failed write rolls everything back.
  - Prints a SIX-LINE summary. Exit codes: 0 done, 2 nothing to do / not found, 3 bad zip, 11 bot running, 12 market open, 1 failed.
    --check prints one line instead: 0 the folder already has this zip's code (this very zip was applied and not undone: later
    fixes on the PC are never reverted; else every file the same), 10 an update is due (also: this zip is in, but a live_model*.json
    it kept is an older repo version), 13 the zip is OLDER than the folder's last update (applied before a newer one, or dated
    before it: never put back over newer code), 2 / 3 as above. It changes nothing.
Stdlib only, no zoneinfo (Windows has no time-zone database without the tzdata package).
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP_GLOB = "OLYMPUS_BACKUP_*.zip"
BACKUP_REL = os.path.join("backups", "update_from_zip")
KEEP_BACKUPS = 5
MARKERS = ("engine/lit.py", "live_model.json", "server.py")          # a zip / folder without these is not this project
# local-only: never written, whatever the zip holds (the owner's keys, switches, state and history)
HARD_LOCAL = ("data/alerts.json", "data/tv.json", "data/tv_device.json", "data/autostart.json", "data/live_state.json", "data/live_state*.json",
              "data/memory.db", "data/memory.db-*", ".env", ".env.*", "*.env", "data/nt_bars/", "logs/", "backups/", ".git/", "data/pc_publish/",
              "data/account_b.json", "data/account_c.json", "data/fleet.json", "data/eval_anchor.json", "data/push.json", "netlify.json", ".olympus/")
KEEP_IF_CHANGED = ("live_model*.json",)                              # root level: the owner's own values win
VERSIONS_REL = "tools/model_versions.json"                          # the repo's own versions of them (tools/model_versions.py)
EOL_STRICT = (".bat", ".cmd", ".ps1")                                # their line endings matter to Windows: never "the same but for line ends"
STATE_SKIP_DIRS = {".git", "logs", "backups", "__pycache__", "node_modules", "nt_bars", "pc_publish", ".claude"}
EXIT_OK, EXIT_FAIL, EXIT_NOTHING, EXIT_BADZIP, EXIT_RUNNING, EXIT_MARKET = 0, 1, 2, 3, 11, 12
EXIT_DUE, EXIT_OLDER = 10, 13                                        # --check only
NEXT_WORDS = "next double-click SETUP_EVERYTHING.bat (or GO_LIVE_EVAL.bat to go live)."


def say(tag: str, text: str) -> None:
    print(f" [{tag}] {text}", flush=True)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------ New York time, no tz database
def _nth_sunday(year: int, month: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(6 - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def et_now(now: float | None = None) -> dt.datetime:
    """US Eastern wall time: daylight time from the 2nd Sunday of March 07:00 UTC to the 1st Sunday of November 06:00 UTC."""
    u = dt.datetime.fromtimestamp(time.time() if now is None else now, dt.timezone.utc).replace(tzinfo=None)
    start = dt.datetime.combine(_nth_sunday(u.year, 3, 2), dt.time(7))
    end = dt.datetime.combine(_nth_sunday(u.year, 11, 1), dt.time(6))
    return u - dt.timedelta(hours=4 if start <= u < end else 5)


def market_open(now: float | None = None) -> bool:
    """CME equity-index futures: Sunday 18:00 ET to Friday 17:00 ET, with a break 17:00-18:00 ET every day."""
    e = et_now(now)
    wd, mod = e.weekday(), e.hour * 60 + e.minute            # Monday = 0
    if wd == 5:
        return False
    if wd == 6:
        return mod >= 18 * 60
    if wd == 4:
        return mod < 17 * 60
    return not (17 * 60 <= mod < 18 * 60)


def bot_running(port: int) -> bool:
    """The bot's dashboard server listens on the port while START_BOT is up (STOP_BOT.bat stops the server and its supervisor)."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.5):
            return True
    except OSError:
        return False


# ------------------------------------------------------------------------------------------------ what is local-only
def ignore_patterns(*texts: str) -> list[str]:
    out = []
    for text in texts:
        for ln in (text or "").splitlines():
            s = ln.strip()
            if s and not s.startswith("#") and not s.startswith("!"):        # a "!" (un-ignore) line is skipped: more is protected, never less
                out.append(s)
    return out


_RX: dict = {}


def _pat_regex(p: str):
    """A gitignore glob as a regex: * and ? stay inside one path part, ** crosses parts."""
    rx = _RX.get(p)
    if rx is None:
        out, i = "", 0
        while i < len(p):
            c = p[i]
            if c == "*":
                if p[i:i + 2] == "**":
                    out += ".*"
                    i += 2
                    if p[i:i + 1] == "/":
                        i += 1
                    continue
                out += "[^/]*"
            elif c == "?":
                out += "[^/]"
            elif c == "[":
                j = p.find("]", i + 2)
                if j < 0:
                    out += re.escape(c)
                else:
                    body = p[i + 1:j]
                    out += "[" + ("^" + body[1:] if body[:1] == "!" else body).replace("\\", "\\\\") + "]"
                    i = j
            else:
                out += re.escape(c)
            i += 1
        rx = _RX[p] = re.compile(out + r"\Z")
    return rx


def matches(rel: str, patterns) -> str | None:
    """The first pattern (gitignore style) that names `rel` (forward slashes) or one of its parent folders. Letter case is ignored (Windows)."""
    parts = rel.split("/")
    prefixes = ["/".join(parts[:i]) for i in range(1, len(parts) + 1)]
    low = [p.lower() for p in prefixes]
    for pat in patterns:
        dir_only = pat.endswith("/")
        p = pat.rstrip("/").lstrip("/").lower()
        if not p:
            continue
        anchored = "/" in p or pat.startswith("/")
        rx = _pat_regex(p)
        cands = low[:-1] if dir_only else low
        for c in cands:
            if rx.match(c if anchored else c.rsplit("/", 1)[-1]):
                return pat
    return None


def is_model(rel: str) -> bool:
    return "/" not in rel and any(_pat_regex(p).match(rel.lower()) for p in KEEP_IF_CHANGED)


def safe_rel(name: str) -> str | None:
    """A zip member as a safe relative path, or None (absolute, a drive letter, '..', a backslash trick)."""
    n = name.replace("\\", "/")
    if not n or n.startswith("/") or re.match(r"^[A-Za-z]:", n) or n.endswith("/"):
        return None
    parts = n.split("/")
    if any(p in ("", ".", "..") for p in parts) or any(ch in n for ch in '<>"|?*\0') or ":" in n:
        return None
    return n


def same_content(rel: str, a: bytes, b: bytes) -> bool:
    if a == b:
        return True
    if rel.lower().endswith(EOL_STRICT) or b"\0" in a[:8192] or b"\0" in b[:8192]:
        return False
    return a.replace(b"\r\n", b"\n") == b.replace(b"\r\n", b"\n")       # a Windows checkout has CRLF, the zip has LF: the same file


def same_json(a: bytes, b: bytes) -> bool:
    try:
        return json.loads(a.decode("utf-8-sig")) == json.loads(b.decode("utf-8-sig"))
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------ live_model*.json: the repo's own versions
def model_sha(data: bytes) -> str:
    """The SHA-256 tools/model_versions.json lists for a live_model*.json: the bytes without a UTF-8 BOM and with Windows line ends
    as LF (a Windows checkout, or an editor's save, of the same file is the same version). tools/model_versions.py uses this too."""
    if data[:3] == b"\xef\xbb\xbf":
        data = data[3:]
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def parse_versions(raw) -> dict | None:
    """tools/model_versions.json -> {file name in lower case: {sha256, ...}}; None when it is missing, not JSON or not format 1."""
    try:
        d = json.loads(raw.decode("utf-8-sig")) if raw else None
    except Exception:
        return None
    if not isinstance(d, dict) or d.get("v") != 1 or not isinstance(d.get("files"), dict):
        return None
    out = {}
    for name, shas in d["files"].items():
        if isinstance(name, str) and isinstance(shas, list):
            out[name.lower()] = {s.lower() for s in shas if isinstance(s, str) and re.fullmatch(r"[0-9a-fA-F]{64}", s)}
    return out


def known_versions(folder: str, z: zipfile.ZipFile) -> tuple[dict | None, str | None]:
    """(versions, 'zip' | 'folder'): the zip's tools/model_versions.json, else the bot folder's own copy; (None, None) without one."""
    try:
        v = parse_versions(z.read(VERSIONS_REL))
    except Exception:                                                   # not in the zip (KeyError) or unreadable
        v = None
    if v is not None:
        return v, "zip"
    try:
        with open(os.path.join(folder, *VERSIONS_REL.split("/")), "rb") as fh:
            v = parse_versions(fh.read())
    except OSError:
        v = None
    return (v, "folder") if v is not None else (None, None)


def model_action(rel: str, old: bytes, new: bytes, known: dict | None) -> str:
    """A root live_model*.json: 'same' (the same values), 'replace' (one of the repo's own older versions: nothing on the PC writes
    these files, so it is an un-updated copy, never the owner's edit) or 'keep' (other values: the owner's own; or no list to tell)."""
    if old == new or same_json(old, new):
        return "same"
    if known and model_sha(old) in known.get(rel.lower(), ()):
        return "replace"
    return "keep"


# ------------------------------------------------------------------------------------------------ the zip
def find_zip(folder: str, given: str | None) -> str | None:
    if given:
        return given if os.path.isfile(given) else None
    home = os.path.expanduser("~")
    places = [folder, os.path.join(home, "Downloads"), os.path.join(home, "Desktop"), os.path.join(home, "OneDrive", "Downloads"),
              os.path.join(home, "OneDrive", "Desktop"), os.path.join(home, "iCloudDrive", "OLYMPUS_BACKUPS"), os.path.join(home, "iCloudDrive")]
    found = []
    for d in places:
        found += [p for p in glob.glob(os.path.join(d, ZIP_GLOB)) if os.path.isfile(p)]
    return max(found, key=os.path.getmtime) if found else None


def expected_sha(zip_path: str) -> tuple[str | None, str | None]:
    """(sha, file) from a *.sha256*.txt next to the zip whose line names it ("<sha>  <name>  <size> MB", tools/make_backup.py).
    A browser's second download is "name (1).zip" / "name.sha256 (1).txt": the " (1)" is ignored on both."""
    d, base = os.path.dirname(os.path.abspath(zip_path)), os.path.basename(zip_path)
    plain = re.sub(r" \(\d+\)(?=\.zip$)", "", base, flags=re.I)
    first = os.path.join(d, plain[:-4] + ".sha256.txt")
    cands = ([first] if os.path.isfile(first) else []) + sorted(p for p in glob.glob(os.path.join(d, "*.sha256*.txt")) if p != first)
    for p in cands:
        try:
            with open(p, encoding="utf-8-sig", errors="replace") as fh:
                for ln in fh:
                    m = re.match(r"^\s*([0-9a-fA-F]{64})\s+\*?(\S.*?)\s*$", ln)
                    if m and any(m.group(2) == n or m.group(2).startswith(n + " ") for n in (base, plain)):
                        return m.group(1).lower(), p
        except OSError:
            continue
    return None, None


def check_zip(zip_path: str) -> tuple[str, str, str | None]:
    """('ok' | 'bad', the words for line 1, the reason when bad)."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = set(z.namelist())
            broken = z.testzip()
    except (zipfile.BadZipFile, OSError) as e:
        return "bad", "", f"the zip does not open ({e.__class__.__name__}). Download it again."
    if broken:
        return "bad", "", f"the zip is damaged (first bad file: {broken}). Download it again."
    missing = [m for m in MARKERS if m not in names]
    if missing:
        return "bad", "", f"this is not the bot's code zip (no {missing[0]} in it)."
    want, src = expected_sha(zip_path)
    if not want:
        return "ok", "SHA-256 not checked (no .sha256.txt next to it)", None
    got = sha256_file(zip_path)
    if got != want:
        return "bad", "", f"SHA-256 does NOT match {os.path.basename(src)} (the download is damaged or it is another file). Download both again."
    return "ok", "SHA-256 OK", None


# ------------------------------------------------------------------------------------------------ the plan
def looks_like_bot(folder: str) -> bool:
    return all(os.path.exists(os.path.join(folder, m.replace("/", os.sep))) for m in MARKERS)


def make_plan(folder: str, z: zipfile.ZipFile) -> dict:
    local_ignore = ""
    try:
        with open(os.path.join(folder, ".gitignore"), encoding="utf-8", errors="replace") as fh:
            local_ignore = fh.read()
    except OSError:
        pass
    zip_ignore = z.read(".gitignore").decode("utf-8", "replace") if ".gitignore" in z.namelist() else ""
    soft = ignore_patterns(local_ignore, zip_ignore)
    known, src = known_versions(folder, z)
    plan = {"add": [], "replace": [], "same": 0, "kept_local": [], "kept_model": [], "skipped": [], "model_updated": [], "versions_from": src}
    for info in z.infolist():
        if info.is_dir():
            continue
        rel = safe_rel(info.filename)
        if rel is None:
            plan["skipped"].append(info.filename[:120])
            continue
        dest = os.path.join(folder, rel.replace("/", os.sep))
        if matches(rel, HARD_LOCAL):
            plan["kept_local"].append(rel)                      # never written, present or not
            continue
        exists = os.path.isfile(dest)
        if os.path.isdir(dest) or os.path.islink(dest):
            plan["skipped"].append(rel)
            continue
        if exists and matches(rel, soft):
            plan["kept_local"].append(rel)                      # gitignored and already here: the local one stays
            continue
        if not exists:
            plan["add"].append(rel)
            continue
        new = z.read(info)
        with open(dest, "rb") as fh:
            old = fh.read()
        if is_model(rel):
            act = model_action(rel, old, new, known)
            if act == "same":
                plan["same"] += 1
            elif act == "replace":
                plan["replace"].append(rel)                     # an older repo version: the zip's values (backed up like any file)
                plan["model_updated"].append(rel)
            else:
                plan["kept_model"].append(rel)                  # the owner's own values (or no list to tell): keep, and say so
            continue
        if same_content(rel, old, new):
            plan["same"] += 1
        else:
            plan["replace"].append(rel)
    return plan


def models_plan(folder: str, z: zipfile.ZipFile, rels) -> dict:
    """This zip is already in (it is the folder's last update, not undone): only the root live_model*.json that update kept are
    looked at again (an older updater kept every differing one); every other file stays as it is now, so a later fix is kept."""
    known, src = known_versions(folder, z)
    plan = {"add": [], "replace": [], "same": 0, "kept_local": [], "kept_model": [], "skipped": [], "model_updated": [], "versions_from": src}
    names = set(z.namelist())
    for rel in dict.fromkeys(r for r in (rels or []) if isinstance(r, str)):
        dest = os.path.join(folder, rel.replace("/", os.sep))
        if not is_model(rel) or rel not in names or not os.path.isfile(dest) or os.path.islink(dest):
            continue
        try:
            with open(dest, "rb") as fh:
                old = fh.read()
            new = z.read(rel)
        except Exception:
            continue
        act = model_action(rel, old, new, known)
        if act == "replace":
            plan["replace"].append(rel)
            plan["model_updated"].append(rel)
        elif act == "keep":
            plan["kept_model"].append(rel)
        else:
            plan["same"] += 1
    return plan


def last_applied(folder: str, zip_sha: str | None):
    """(stamp, manifest) of this very zip when it is the folder's last finished update that was not undone, else None."""
    done = applied_updates(folder)
    if done and zip_sha and done[-1][1].get("zip_sha256") == zip_sha:
        return done[-1]
    return None


def model_words(plan: dict, dry: bool = False) -> tuple[str, str]:
    """(the words for line 3 after the counts, the words for line 4) about the root live_model*.json files."""
    up, kept = plan.get("model_updated") or [], plan.get("kept_model") or []
    changed = ""
    if up:
        older = "yours is an older version" if len(up) == 1 else "yours are older versions"
        changed = f"; {short(up)}: " + (f"would get the new values ({older})" if dry else
                                         f"updated to the new values ({'yours was an older version' if len(up) == 1 else 'yours were older versions'})")
    if not kept:
        return changed, ""
    if plan.get("versions_from"):
        return changed, f"{short(kept)}: your own values (no version the repo ever had), YOURS kept"
    return changed, f"{short(kept)}: your values differ from the zip, YOURS kept"


def state_list(folder: str, out_path: str) -> int:
    """The folder as it is now: size, modified time (UTC), path. Cheap (no hashing); heavy / local folders are named, not walked."""
    n = 0
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# bot folder state before the update: size_bytes\tmodified_utc\tpath\n")
        for root, dirs, files in os.walk(folder):
            for d in sorted(dirs):
                if d in STATE_SKIP_DIRS:
                    fh.write(f"-\t-\t{os.path.relpath(os.path.join(root, d), folder).replace(os.sep, '/')}/ (not listed)\n")
            dirs[:] = sorted(d for d in dirs if d not in STATE_SKIP_DIRS)
            for f in sorted(files):
                p = os.path.join(root, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                fh.write(f"{st.st_size}\t{dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\t{os.path.relpath(p, folder).replace(os.sep, '/')}\n")
                n += 1
    return n


def write_file(dest: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    tmp = dest + ".upd-tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except OSError:
            pass
    os.replace(tmp, dest)


def rollback(folder: str, bdir: str, man: dict) -> list[str]:
    """Put back what an update did. Returns the paths it could not restore / left in place."""
    left = []
    for rel in man.get("replaced", []):
        src = os.path.join(bdir, "files", rel.replace("/", os.sep))
        try:
            with open(src, "rb") as fh:
                write_file(os.path.join(folder, rel.replace("/", os.sep)), fh.read())
        except OSError:
            left.append(rel)
    for rel in man.get("added", []):
        p = os.path.join(folder, rel.replace("/", os.sep))
        try:
            if not os.path.isfile(p):
                continue
            if sha256_file(p) != (man.get("written") or {}).get(rel):
                left.append(rel + " (changed since the update: kept)")
                continue
            os.remove(p)
            d = os.path.dirname(p)
            while d and os.path.abspath(d) != os.path.abspath(folder) and not os.listdir(d):
                os.rmdir(d)
                d = os.path.dirname(d)
        except OSError:
            left.append(rel)
    return left


def prune_backups(root: str) -> None:
    try:
        dirs = sorted(d for d in os.listdir(root) if os.path.isfile(os.path.join(root, d, "manifest.json")))
    except OSError:
        return
    for d in dirs[:-KEEP_BACKUPS]:
        shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def short(items, n=3) -> str:
    items = list(items)
    return ", ".join(items[:n]) + (f" and {len(items) - n} more" if len(items) > n else "")


def six(lines) -> None:
    print("", flush=True)
    for i, (k, v) in enumerate(lines, 1):
        print(f" {i}. {k:<8}{v}", flush=True)
    print("", flush=True)


# ------------------------------------------------------------------------------------------------ update
def guards(a, folder: str) -> int:
    if a.force:
        return EXIT_OK
    if bot_running(a.port):
        say("STOP", f"The bot is running (its server answers on port {a.port}). Nothing was changed.")
        say("FIX", "Double-click STOP_BOT.bat first (never during an open trade), then run this again.")
        return EXIT_RUNNING
    if not a.allow_market_open and market_open(a.now):
        e = et_now(a.now)
        say("STOP", f"The futures market is open ({e.strftime('%a %H:%M')} ET). Nothing was changed.")
        say("FIX", "Best time: 17:00-18:00 ET on a weekday, or the weekend. The bot is stopped, so you may also go on now.")
        return EXIT_MARKET
    return EXIT_OK


def update(a) -> int:
    folder = os.path.abspath(a.folder)
    if not looks_like_bot(folder):
        say("FIX", f"{folder} is not the bot folder (no {MARKERS[0]} / {MARKERS[1]} in it). Put UPDATE_FROM_ZIP.bat in the bot folder.")
        return EXIT_NOTHING
    zip_path = find_zip(folder, a.zip)
    if not zip_path:
        say("FIX", (f"{a.zip} was not found." if a.zip else f"No {ZIP_GLOB} in the bot folder, Downloads or Desktop.") + " Download the code zip to the PC first (or drag it onto UPDATE_FROM_ZIP.bat).")
        return EXIT_NOTHING
    zip_path = os.path.abspath(zip_path)
    print(f" zip:    {zip_path}\n folder: {folder}", flush=True)
    state, sha_words, why = check_zip(zip_path)
    if state != "ok":
        say("STOP", why + " Nothing was changed.")
        return EXIT_BADZIP
    rc = guards(a, folder)
    if rc:
        return rc
    with zipfile.ZipFile(zip_path) as z:
        zip_sha = sha256_file(zip_path)
        prev = last_applied(folder, zip_sha)                     # this very zip is already in: only its kept live_model*.json again
        plan = models_plan(folder, z, prev[1].get("kept_model")) if prev else make_plan(folder, z)
        n_change = len(plan["add"]) + len(plan["replace"])
        model_changed, model_kept = model_words(plan, dry=a.dry_run)
        kept_words = [model_kept] if model_kept else []
        if prev:
            kept_words.append(f"the rest of this zip went in on {prev[0]}: anything changed on the PC since stays as it is")
        kept_words.append(f"{len(plan['kept_local'])} local-only file{'s' if len(plan['kept_local']) != 1 else ''} in the zip left alone" if plan["kept_local"] else "your local-only files untouched")
        if plan["skipped"]:
            kept_words.append(f"{len(plan['skipped'])} odd path{'s' if len(plan['skipped']) != 1 else ''} skipped")
        line1 = ("Zip", f"{os.path.basename(zip_path)}  ({sha_words})")
        line2 = ("Folder", folder)
        if prev:
            line3_words = f"{len(plan['replace'])} updated, 0 new (this zip is already in: only its live_model*.json are looked at again)" + model_changed
        else:
            line3_words = f"{len(plan['replace'])} updated, {len(plan['add'])} new, {plan['same']} already the same" + model_changed
        if a.dry_run or not n_change:
            six([line1, line2, ("Changed", ("would be: " if n_change else "nothing to do: ") + line3_words), ("Kept", "; ".join(kept_words)),
                 ("Backup", "none (nothing was changed)"), ("Next", "dry run: run it without --dry-run to update" if n_change else
                                                             ("the folder already has this zip's code" if prev else "the folder already matches the zip"))])
            return EXIT_OK
        need = sum(os.path.getsize(os.path.join(folder, r.replace("/", os.sep))) for r in plan["replace"]) + sum(z.getinfo(r).file_size for r in plan["add"] + plan["replace"])
        try:
            free = shutil.disk_usage(folder).free
        except OSError:
            free = None
        if free is not None and free < need + (200 << 20):
            say("STOP", f"Not enough free disk space ({free >> 20} MB free, about {(need >> 20) + 200} MB needed). Nothing was changed.")
            return EXIT_FAIL
        stamp = dt.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d_%H%M%S")
        broot = os.path.join(folder, BACKUP_REL)
        bdir = os.path.join(broot, stamp)
        os.makedirs(os.path.join(bdir, "files"), exist_ok=True)
        n_state = state_list(folder, os.path.join(bdir, "state_before.txt"))
        man = {"v": 1, "stamp": stamp, "zip": os.path.basename(zip_path), "zip_sha256": zip_sha, "sha_check": sha_words, "folder": folder, "state_files": n_state,
               "replaced": [], "added": [], "written": {}, "before": {}, "kept_model": plan["kept_model"], "model_updated": plan["model_updated"],
               "versions_from": plan["versions_from"], "only_models": bool(prev), "kept_local": plan["kept_local"][:500], "skipped": plan["skipped"][:100],
               "undone": False, "done": False}

        def save_man():
            with open(os.path.join(bdir, "manifest.json"), "w", encoding="utf-8") as fh:
                json.dump(man, fh, indent=1)

        try:
            for rel in plan["replace"]:                           # 1. copy every file that will change, before any write
                src = os.path.join(folder, rel.replace("/", os.sep))
                dst = os.path.join(bdir, "files", rel.replace("/", os.sep))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                man["before"][rel] = sha256_file(dst)
            save_man()
            for rel in plan["replace"] + plan["add"]:             # 2. write
                data = z.read(rel)
                (man["replaced"] if rel in man["before"] else man["added"]).append(rel)
                man["written"][rel] = hashlib.sha256(data).hexdigest()
                write_file(os.path.join(folder, rel.replace("/", os.sep)), data)
            man["done"] = True
            save_man()
        except Exception as e:                                    # a locked file, a full disk: put everything back
            left = rollback(folder, bdir, man)
            man["undone"] = True
            man["error"] = f"{e.__class__.__name__}: {e}"[:300]
            save_man()
            say("STOP", f"A file could not be written ({e.__class__.__name__}: {str(e)[:160]}). Everything was put back" + (f" except {short(left)}." if left else "."))
            say("FIX", "Close anything that has the bot folder open (the bot, an editor, NinjaTrader add-on export), then run it again.")
            return EXIT_FAIL
    prune_backups(broot)
    req = any(r.startswith("requirements") and r.endswith(".txt") and "/" not in r for r in man["replaced"] + man["added"])
    pip_words = ""
    if req and a.pip:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(folder, "requirements.txt")], capture_output=True, text=True)
        pip_words = " Packages installed." if r.returncode == 0 else " Packages did NOT install: run ONE_TIME_SETUP.bat."
    elif req:
        pip_words = " requirements.txt changed: run ONE_TIME_SETUP.bat once."
    six([line1, line2, ("Changed", line3_words), ("Kept", "; ".join(kept_words)),
         ("Backup", f"{os.path.join(BACKUP_REL, stamp)}  ({len(man['replaced'])} old files saved; UNDO_UPDATE.bat puts them back)"),
         ("Next", "done. The bot was NOT started: " + (a.next or NEXT_WORDS) + pip_words)])
    return EXIT_OK


# ------------------------------------------------------------------------------------------------ undo
def undo(a) -> int:
    folder = os.path.abspath(a.folder)
    broot = os.path.join(folder, BACKUP_REL)
    try:
        stamps = sorted(d for d in os.listdir(broot) if os.path.isfile(os.path.join(broot, d, "manifest.json")))
    except OSError:
        stamps = []
    pick, man = None, None
    for s in reversed(stamps):
        try:
            with open(os.path.join(broot, s, "manifest.json"), encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            continue
        if not m.get("undone"):
            pick, man = s, m
            break
    if not pick:
        say("OK", "Nothing to undo: no update from a zip is saved in backups\\update_from_zip.")
        return EXIT_NOTHING
    if not a.force and bot_running(a.port):
        say("STOP", f"The bot is running (its server answers on port {a.port}). Nothing was changed.")
        say("FIX", "Double-click STOP_BOT.bat first, then run UNDO_UPDATE.bat again.")
        return EXIT_RUNNING
    bdir = os.path.join(broot, pick)
    models_back = [r for r in man.get("replaced", []) if isinstance(r, str) and is_model(r)]      # the update gave them the new values
    if a.dry_run:
        six([("Undo", f"the update of {pick} ({man.get('zip')})"), ("Folder", folder), ("Changed", f"would put back {len(man.get('replaced', []))} files and remove {len(man.get('added', []))} new ones"),
             ("Kept", f"your local-only files are not touched; {short(models_back)} would go back to the values before the update" if models_back else
              "your local-only files and live_model*.json are not touched"), ("Backup", os.path.join(BACKUP_REL, pick)), ("Next", "dry run: run it without --dry-run to undo")])
        return EXIT_OK
    left = rollback(folder, bdir, man)
    man["undone"] = True
    man["undone_at"] = dt.datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(bdir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1)
    n_back, n_gone = len(man.get("replaced", [])), len(man.get("added", []))
    six([("Undo", f"the update of {pick} ({man.get('zip')})"), ("Folder", folder), ("Changed", f"{n_back} files put back, {n_gone - sum(1 for x in left if 'kept' in x)} new files removed"),
         ("Kept", (f"could not undo: {short(left)}" if left else f"your local-only files were not touched; {short(models_back)} back to the values before the update" if models_back
                   else "your local-only files and live_model*.json were not touched")), ("Backup", f"{os.path.join(BACKUP_REL, pick)} (kept)"),
         ("Next", "done. The bot was NOT started: start it yourself with GO_LIVE_EVAL.bat when you are ready.")])
    return EXIT_FAIL if any("kept" not in x for x in left) else EXIT_OK


# ------------------------------------------------------------------------------------------------ check (SETUP_EVERYTHING step 1)
def zip_day(name: str | None) -> str | None:
    """The YYYY-MM-DD in an OLYMPUS_BACKUP_<date>_<commit>.zip name (tools/make_backup.py, tools/second_backup.py), else None."""
    m = re.search(r"OLYMPUS_BACKUP_(\d{4}-\d{2}-\d{2})", os.path.basename(str(name or "")))
    return m.group(1) if m else None


def applied_updates(folder: str) -> list:
    """The folder's finished updates that were not undone, oldest first: [(stamp, manifest)] (backups/update_from_zip/<stamp>/)."""
    broot = os.path.join(folder, BACKUP_REL)
    try:
        stamps = sorted(d for d in os.listdir(broot) if os.path.isfile(os.path.join(broot, d, "manifest.json")))
    except OSError:
        return []
    out = []
    for st in stamps:
        try:
            with open(os.path.join(broot, st, "manifest.json"), encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(m, dict) and m.get("done") and not m.get("undone"):
            out.append((st, m))
    return out


def kept_models_due(folder: str, zip_path: str, rels) -> list:
    """The live_model*.json an earlier update of this very zip kept that the list now shows are older repo versions ([] if none)."""
    if not rels:
        return []
    try:
        with zipfile.ZipFile(zip_path) as z:
            return models_plan(folder, z, rels)["model_updated"]
    except Exception:
        return []


def check(a) -> int:
    """Read only, no bot / market guard: does the folder already have this zip's code? One line, the exit code says it."""
    folder = os.path.abspath(a.folder)
    if not looks_like_bot(folder):
        say("FIX", f"{folder} is not the bot folder (no {MARKERS[0]} / {MARKERS[1]} in it).")
        return EXIT_NOTHING
    zip_path = find_zip(folder, a.zip)
    if not zip_path:
        say("FIX", (f"{a.zip} was not found." if a.zip else f"No {ZIP_GLOB} in the bot folder, Downloads or Desktop.") + " Download the code zip to the PC first.")
        return EXIT_NOTHING
    zip_path = os.path.abspath(zip_path)
    name, done = os.path.basename(zip_path), applied_updates(folder)
    if done:                                                  # this very zip applied before (fast: no unpacking at all)
        try:
            sha = sha256_file(zip_path)
        except OSError:
            sha = None
        hits = [i for i, (_st, m) in enumerate(done) if sha and m.get("zip_sha256") == sha]
        if hits and hits[-1] == len(done) - 1:
            due = kept_models_due(folder, zip_path, done[-1][1].get("kept_model"))
            if due:                                           # an older updater kept them; the zip's list says they are old repo versions
                say("..", f"{name}: this code is in (applied {done[-1][0]}), but {short(due)} {'is an older version' if len(due) == 1 else 'are older versions'}"
                          " of the repo's: an update is due (the new values; nothing else is changed).")
                return EXIT_DUE
            say("OK", f"{name}: the bot folder already has this code (applied {done[-1][0]}, not undone).")
            return EXIT_OK
        if hits:
            say("OK", f"{name} was applied on {done[hits[-1]][0]}, then the newer {done[-1][1].get('zip')}: it is not put back over it.")
            return EXIT_OLDER
    state, sha_words, why = check_zip(zip_path)
    if state != "ok":
        say("STOP", why + " Nothing was changed.")
        return EXIT_BADZIP
    last = str(done[-1][1].get("zip") or "") if done else None
    if zip_day(last) and zip_day(name) and zip_day(name) < zip_day(last):
        say("OK", f"{name} is older than the code this folder already took from {last}: it is not put back over it.")
        return EXIT_OLDER
    with zipfile.ZipFile(zip_path) as z:
        plan = make_plan(folder, z)
    n_rep, n_add = len(plan["replace"]), len(plan["add"])
    if n_rep or n_add:
        up = plan["model_updated"]
        extra = f"; {short(up)}: the new values (yours {'is an older version' if len(up) == 1 else 'are older versions'})" if up else ""
        say("..", f"{name}: an update is due ({n_rep} updated, {n_add} new{extra}; {sha_words}).")
        return EXIT_DUE
    say("OK", f"{name}: the bot folder already has this code ({plan['same']} files the same; {sha_words}).")
    return EXIT_OK


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Update the bot folder from a code zip (no GitHub). See the top of this file.")
    ap.add_argument("zip", nargs="?", default=None)
    ap.add_argument("--folder", default=HERE)
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--allow-market-open", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--pip", action="store_true", help="install requirements.txt when the update changed it")
    ap.add_argument("--check", action="store_true", help="read only: is an update due? (exit 0 no, 10 yes, 13 the zip is older)")
    ap.add_argument("--next", default=None, help=argparse.SUPPRESS)                     # SETUP_EVERYTHING: its own words for line 6
    ap.add_argument("--now", type=float, default=None, help=argparse.SUPPRESS)          # tests: the clock
    a = ap.parse_args(argv)
    if a.zip is not None and not a.zip.strip():
        a.zip = None
    if a.port <= 0:
        try:
            a.port = int(os.environ.get("PORT") or 8766)
        except ValueError:
            a.port = 8766
    try:
        if a.check:
            return check(a)
        return undo(a) if a.undo else update(a)
    except KeyboardInterrupt:
        say("STOP", "Stopped by you.")
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
