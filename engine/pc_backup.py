"""Disaster recovery for the PC's private state (day-ops2 2026-11-26; lead: "a dead PC costs one evening, not a week").

The code is in GitHub; what is NOT is the PC's own state: the account set-up (data/accounts.json, start_bot.json, rapid*.json,
lit25.json, account_b.json, nt_accounts_allow.json, keepalive.json, combo / lanes / switches, the ledgers and day state the bot
keeps under data/) and %USERPROFILE%\\.olympus (alerts.json = the Telegram / Discord set-up, kalshi files, ...). This module packs
them WEEKLY into ONE encrypted file:

  * encrypted with Fernet (AES-128-CBC + HMAC-SHA256, the `cryptography` package already in requirements.txt) under a random key
    made on the PC and kept ONLY there (%USERPROFILE%\\.olympus\\backup.key). The key never leaves the PC by itself: START /
    `--show-key` shows it as a recovery code the owner saves ONCE in his phone's notes / password manager (without it nobody,
    Claude included, can open the backup; a dead PC + a lost code = the backup is useless, so the code matters).
  * written to the backup folder: data/pc_backup.json "dir", else %OneDrive%\\Olympus Backup (the cloud keeps a copy off the
    PC, encrypted), else Documents\\Olympus Backup. The newest KEEP files stay.
  * NEVER in it: data/auto_resume.json and data/autostart.json (the proofs that arm a real account: on a new PC the owner types
    START + the phrase himself), the bot's transient files (locks, .tmp, remote / Telegram command state), tick / depth / bar
    caches, logs, and backup.key itself.

  python -X utf8 -m engine.pc_backup --now            make one now (also what the weekly self-heal run does)
  python -X utf8 -m engine.pc_backup --list           the backups in the folder
  python -X utf8 -m engine.pc_backup --show-key       the recovery code (on the PC screen only)
  python -X utf8 -m engine.pc_backup --restore FILE --key CODE [--force]   on the NEW PC (tools/bat/RESTORE_NEW_PC.bat asks both)
Restore checks every file's SHA-256 against the sealed manifest, never touches a tracked file, keeps any file it would replace as
<name>.before-restore, and prints the next steps (ALERTS test, START BOT + your phrase). Tests: tests.test_ops2 (sandbox).
"""
from __future__ import annotations

import base64
import datetime as dt
import fnmatch
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import zipfile
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = 1
KEY_NAME = "backup.key"
EXT = ".olb"
KEEP = 8
EVERY_S = 7 * 86400
MAX_FILE = 5 * 1024 * 1024
MAX_TOTAL = 60 * 1024 * 1024
STATE_REL = os.path.join("logs", "self_heal", "pc_backup.json")
NEVER = ("data/auto_resume.json", "data/autostart.json", "data/remote_done.json", "data/tg_cmd.json", "data/*.tmp", "*.tmp",
         "*.lock", "data/ticks/*", "data/depth/*", "data/nt_bars/*", "data/orderflow*", "data/tickrec*", "data/cache/*",
         "data/*/cache/*", "*.parquet", "*.zip", "*.gz", "__pycache__/*", "*.pyc", "*.before-restore", "data/kalshi*/tape*")
HOME_NEVER = (KEY_NAME, "*.tmp", "*.lock", "*.zip", "cache/*", "logs/*")
EXTRA = (".env.local.ps1",)                     # bot-folder files outside data/ (git-ignored, the owner's live switch)


def home(env=None) -> str:
    e = os.environ if env is None else env
    return e.get("OLYMPUS_HOME") or os.path.join(e.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


def _match(rel: str, pats) -> bool:
    return any(fnmatch.fnmatchcase(rel, p) for p in pats)


def _ignored(root: str, rels: list) -> set:
    """The paths git ignores (only those may be in a backup: a tracked file comes back from GitHub)."""
    if not rels:
        return set()
    try:
        r = subprocess.run(["git", "check-ignore", "--no-index", "--stdin"], cwd=root, input="\n".join(rels), capture_output=True,
                           text=True, timeout=60)
        return {ln.strip() for ln in r.stdout.splitlines() if ln.strip()}
    except Exception:  # noqa: BLE001
        return set()


def collect(root: str = ROOT, env=None) -> list:
    """[(archive name, absolute path)]: "bot/<rel>" for the git-ignored files under data/ (+ EXTRA), "home/<rel>" for .olympus."""
    cand = []
    d = os.path.join(root, "data")
    for base, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for f in files:
            p = os.path.join(base, f)
            rel = os.path.relpath(p, root).replace("\\", "/")
            if _match(rel, NEVER):
                continue
            try:
                if os.path.getsize(p) > MAX_FILE:
                    continue
            except OSError:
                continue
            cand.append(rel)
    for x in EXTRA:
        if os.path.isfile(os.path.join(root, x)):
            cand.append(x)
    ign = _ignored(root, cand)
    out = [(f"bot/{rel}", os.path.join(root, rel)) for rel in sorted(cand) if rel in ign]
    h = home(env)
    if os.path.isdir(h):
        for base, dirs, files in os.walk(h):
            for f in files:
                p = os.path.join(base, f)
                rel = os.path.relpath(p, h).replace("\\", "/")
                if _match(rel, HOME_NEVER):
                    continue
                try:
                    if os.path.getsize(p) > MAX_FILE:
                        continue
                except OSError:
                    continue
                out.append((f"home/{rel}", p))
    total, keep = 0, []
    for name, p in out:
        try:
            total += os.path.getsize(p)
        except OSError:
            continue
        if total > MAX_TOTAL:
            break
        keep.append((name, p))
    return keep


# ------------------------------------------------------------------------------------------------ the key
def key_path(env=None) -> str:
    return os.path.join(home(env), KEY_NAME)


def get_key(env=None, make: bool = True) -> bytes | None:
    p = key_path(env)
    try:
        with open(p, "rb") as fh:
            k = fh.read().strip()
        if k:
            return k
    except OSError:
        pass
    if not make:
        return None
    from cryptography.fernet import Fernet
    k = Fernet.generate_key()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(k)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return k


def recovery_code(key: bytes) -> str:
    """The key as the owner writes it down: groups of 4 separated by spaces (spaces are ignored on restore; '-' and '_' are part
    of the key itself)."""
    t = key.decode()
    return " ".join(t[i:i + 4] for i in range(0, len(t), 4))


def parse_code(code: str) -> bytes:
    t = "".join(ch for ch in str(code or "") if ch not in " \t\r\n")
    base64.urlsafe_b64decode(t.encode())          # raises on junk
    return t.encode()


# ------------------------------------------------------------------------------------------------ backup / restore
def target_dir(root: str = ROOT, env=None) -> str:
    e = os.environ if env is None else env
    try:
        with open(os.path.join(root, "data", "pc_backup.json"), encoding="utf-8") as fh:
            d = (json.load(fh) or {}).get("dir")
        if d:
            return d
    except Exception:  # noqa: BLE001
        pass
    od = e.get("OneDrive") or e.get("ONEDRIVE")
    if od and os.path.isdir(od):
        return os.path.join(od, "Olympus Backup")
    prof = e.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(prof, "Documents", "Olympus Backup")


def make(root: str = ROOT, env=None, now=None, dest: str | None = None) -> dict:
    """One encrypted backup. {"ok", "path", "files", "bytes", "error"}."""
    from cryptography.fernet import Fernet
    now = time.time() if now is None else float(now)
    try:
        files = collect(root, env)
        buf = io.BytesIO()
        man = {"v": VERSION, "made": int(now), "files": {}}
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name, p in files:
                with open(p, "rb") as fh:
                    b = fh.read()
                z.writestr(name, b)
                man["files"][name] = hashlib.sha256(b).hexdigest()
            z.writestr("manifest.json", json.dumps(man, indent=1))
        blob = Fernet(get_key(env)).encrypt(buf.getvalue())
        d = dest or target_dir(root, env)
        os.makedirs(d, exist_ok=True)
        name = "olympus-backup-" + dt.datetime.fromtimestamp(now, ET).strftime("%Y%m%d-%H%M") + EXT
        p = os.path.join(d, name)
        with open(p + ".tmp", "wb") as fh:
            fh.write(blob)
        from .fsutil import replace as _replace
        _replace(p + ".tmp", p)
        old = sorted(f for f in os.listdir(d) if f.startswith("olympus-backup-") and f.endswith(EXT))
        for f in old[:-KEEP]:
            try:
                os.remove(os.path.join(d, f))
            except OSError:
                pass
        return {"ok": True, "path": p, "files": len(files), "bytes": len(blob)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"[:200]}


def restore(path: str, code: str, root: str = ROOT, env=None, force: bool = False) -> dict:
    """Unpack a backup on the new PC. {"ok", "written": [...], "kept": [...], "error"}. Never writes a tracked file or outside
    the bot folder / .olympus; a file it replaces is kept as <name>.before-restore (or, without force, left as it is)."""
    from cryptography.fernet import Fernet, InvalidToken
    try:
        key = parse_code(code)
        with open(path, "rb") as fh:
            raw = Fernet(key).decrypt(fh.read())
    except (InvalidToken, ValueError):
        return {"ok": False, "error": "wrong recovery code, or the file is damaged / not an Olympus backup"}
    except OSError as e:
        return {"ok": False, "error": f"cannot read the backup: {e}"}
    z = zipfile.ZipFile(io.BytesIO(raw))
    man = json.loads(z.read("manifest.json"))
    h = home(env)
    plan, bad = [], []
    for name, sha in man.get("files", {}).items():
        b = z.read(name)
        if hashlib.sha256(b).hexdigest() != sha:
            bad.append(name)
            continue
        kind, _, rel = name.partition("/")
        if ".." in rel.split("/") or rel.startswith("/") or ":" in rel:
            bad.append(name)
            continue
        if kind == "bot":
            if _match(rel, NEVER) or not (rel.startswith("data/") or rel in EXTRA):
                bad.append(name)
                continue
            dst = os.path.join(root, *rel.split("/"))
        elif kind == "home":
            dst = os.path.join(h, *rel.split("/"))
        else:
            bad.append(name)
            continue
        plan.append((name, rel, kind, dst, b))
    if bad:
        return {"ok": False, "error": f"{len(bad)} file(s) failed the check (nothing written): {', '.join(bad[:3])}"}
    tracked = set()
    try:
        r = subprocess.run(["git", "ls-files", "--", *[p[1] for p in plan if p[2] == "bot"]], cwd=root, capture_output=True,
                           text=True, timeout=60)
        tracked = {x.strip() for x in r.stdout.splitlines() if x.strip()}
    except Exception:  # noqa: BLE001
        pass
    written, kept = [], []
    for name, rel, kind, dst, b in plan:
        if kind == "bot" and rel in tracked:
            kept.append(name)
            continue
        if os.path.exists(dst):
            with open(dst, "rb") as fh:
                if fh.read() == b:
                    continue
            if not force:
                kept.append(name)
                continue
            from .fsutil import replace as _replace
            _replace(dst, dst + ".before-restore")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as fh:
            fh.write(b)
        written.append(name)
    return {"ok": True, "written": written, "kept": kept, "made": man.get("made")}


# ------------------------------------------------------------------------------------------------ weekly run (self-heal)
def _state(root):
    try:
        with open(os.path.join(root, STATE_REL), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def due(root: str = ROOT, now=None) -> bool:
    now = time.time() if now is None else float(now)
    e = dt.datetime.fromtimestamp(now, ET)
    m = e.hour * 60 + e.minute
    if e.weekday() < 5 and 110 <= m < 960:
        return False                                  # never in trading hours
    return now - float(_state(root).get("t") or 0) >= EVERY_S


def weekly(root: str = ROOT, env=None, now=None, apply: bool = True) -> dict | None:
    """The self-heal hook: one backup a week outside trading hours. None = not due."""
    now = time.time() if now is None else float(now)
    if not due(root, now):
        return None
    if not apply:
        return {"ok": True, "would": True}
    first = get_key(env, make=False) is None
    r = make(root, env, now)
    st = _state(root)
    st.update(t=int(now), ok=bool(r.get("ok")), files=r.get("files"), path=os.path.basename(str(r.get("path") or "")),
              error=r.get("error"), need_code=bool(st.get("need_code") or first))
    try:
        p = os.path.join(root, STATE_REL)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        from .fsutil import replace as _replace
        _replace(p + ".tmp", p)
    except OSError:
        pass
    return {**r, "first": first}


def code_line(root: str = ROOT, env=None) -> str:
    """START's one line until the owner confirmed he saved the code (data/pc_backup.json "code_saved": true)."""
    try:
        with open(os.path.join(root, "data", "pc_backup.json"), encoding="utf-8") as fh:
            if (json.load(fh) or {}).get("code_saved"):
                return ""
    except Exception:  # noqa: BLE001
        pass
    k = get_key(env, make=False)
    if not k:
        return ""
    return ("[..] Backup recovery code (save it ONCE in your phone's notes; a new PC needs it to restore your accounts): "
            + recovery_code(k) + "   (then: python -X utf8 -m engine.pc_backup --code-saved)")


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if "--now" in a:
        r = make()
        print(f"[OK] backup: {r['path']} ({r['files']} files)" if r.get("ok") else f"[FIX] backup failed: {r.get('error')}")
        return 0 if r.get("ok") else 1
    if "--list" in a:
        d = target_dir()
        fs = sorted(f for f in os.listdir(d) if f.endswith(EXT)) if os.path.isdir(d) else []
        print(d)
        for f in fs:
            print("  " + f)
        return 0
    if "--show-key" in a:
        k = get_key()
        print("Recovery code (keep it private, in your phone's notes / password manager):\n  " + recovery_code(k))
        return 0
    if "--code-saved" in a:
        p = os.path.join(ROOT, "data", "pc_backup.json")
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            d = {}
        d["code_saved"] = True
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(d, open(p, "w", encoding="utf-8"))
        print("[OK] START stops showing the code.")
        return 0
    if "--restore-newest" in a:                      # tools/bat/RESTORE_NEW_PC.bat: the newest file in the backup folder, asked
        d = target_dir()
        fs = sorted(f for f in os.listdir(d) if f.endswith(EXT)) if os.path.isdir(d) else []
        p = input(f"Backup file (Enter = the newest in {d}: {fs[-1] if fs else 'none found'}): ").strip().strip('"')
        p = p or (os.path.join(d, fs[-1]) if fs else "")
        if not p or not os.path.isfile(p):
            print("[FIX] No backup file. Copy your olympus-backup-*.olb onto this PC (OneDrive > Olympus Backup) and type its path.")
            return 1
        a = ["--restore", p] + (["--force"] if "--force" in a else [])
    if "--restore" in a:
        i = a.index("--restore")
        path = a[i + 1] if len(a) > i + 1 else ""
        code = a[a.index("--key") + 1] if "--key" in a and len(a) > a.index("--key") + 1 else input("Recovery code: ")
        r = restore(path, code, force="--force" in a)
        if not r.get("ok"):
            print(f"[FIX] {r.get('error')}")
            return 1
        print(f"[OK] restored {len(r['written'])} file(s)" + (f"; kept your current {len(r['kept'])} (add --force to replace them)"
                                                              if r["kept"] else ""))
        print("Next: ALERTS test (tools\\bat\\TEST_ALERT.bat), then START_BOT.bat and type your phrase: nothing is armed until you do.")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
