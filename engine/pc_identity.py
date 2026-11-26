"""PC IDENTITY (day-noleak 2026-11-26): only the owner's PC posts to the REAL phone channels.

Why: on 2026-11-25 19:43 ET a cloud rehearsal sandbox (new code, paper adapter, no NinjaTrader) started server.py; its report
keeper ran tools/pc_report.py and the sandbox posted a real "DISABLED: bot stopped" to the PUBLIC ntfy status topic. The board
and the lead read it as the owner's PC: a false alarm. A copy of this repo anywhere could do the same.

The rule, may_post(): a real post (ntfy status / alert topics, the push relay, Web Push, Telegram / Discord, data-feed answers)
goes out only
  * on the owner's PC: Windows, and data/pc_identity.json (gitignored) holds THIS machine's fingerprint. The file is written by
    `--adopt`, or adopted once by itself on the first call when the folder shows the PC's own setup: Windows + one of the bot's
    local account files (data/accounts.json, account_b.json, auto_resume.json, autostart.json; all gitignored, made only by the
    owner's own START / ADD_ACCOUNT; the NinjaTrader folder is noted, not required, so the PC never goes dark). A copied folder on
    another machine has another fingerprint: no posts there;
  * or in GitHub Actions (GITHUB_ACTIONS=true: the cloud monitor's own PC-silent / alert jobs, unchanged).
Everything else (a Claude sandbox, a test, a dev Linux box) = dry run: nothing is sent, one log line per process and kind.
LE_NO_POST=1 = never post (anywhere). Fingerprint = sha256 of Windows' MachineGuid (the computer name only when Windows gives
no MachineGuid), first 16 hex; the file never holds either.
  python -X utf8 -m engine.pc_identity            what this machine is (may post or not, why)
  python -X utf8 -m engine.pc_identity --adopt    (on the owner's PC) write the identity now
Tests: tests/test_noleak.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "pc_identity.json")
PC_FILES = ("accounts.json", "account_b.json", "auto_resume.json", "autostart.json",
            # red team 2026-11-26: START BOT's own config (go.CFG) and the account-name files every set-up PC has
            "start_bot.json", "nt_accounts_allow.json", "eval_anchor.json")
_CACHE: dict = {}
_SAID: set = set()
_IS_NT = os.name == "nt"                     # tests flip these (never the real machine)
_GUID = None                                 # tests: a fixed MachineGuid
FORCE = None                                 # tests only: True / False replaces the check (a test that fakes urlopen itself)


def _machine_guid() -> str:
    if _GUID is not None:
        return _GUID
    try:
        import winreg  # noqa: PLC0415  (Windows only)
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                           winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0))
        return str(winreg.QueryValueEx(k, "MachineGuid")[0])
    except Exception:  # noqa: BLE001
        return ""


def fingerprint() -> str:
    g = _machine_guid()                      # MachineGuid alone when Windows gives it (a renamed PC keeps posting); else the name
    raw = f"guid|{g}" if g else f"node|{platform.node().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def node_fingerprint() -> str:
    """The computer-name fingerprint, kept beside fp: a MachineGuid read that fails ONCE (registry busy, a locked-down
    account) must match it instead of silencing the real PC (red team 2026-11-26)."""
    return hashlib.sha256(f"node|{platform.node().lower()}".encode("utf-8")).hexdigest()[:16]


def _owner_profile() -> bool:
    """The owner's alert set-up lives in the Windows USER profile (ALERTS_SETUP.bat -> ~/.olympus/alerts.json), not in the bot
    folder: a copied / synced bot folder does not bring it. With it, a fingerprint change (Windows reinstall, a new MachineGuid,
    a OneDrive copy of pc_identity.json from another machine) re-adopts instead of going dark."""
    try:
        return os.path.isfile(os.path.join(os.path.expanduser("~"), ".olympus", "alerts.json"))
    except Exception:  # noqa: BLE001
        return False


def _nt_folder() -> str | None:
    home = os.path.expanduser("~")
    for base in (os.path.join(home, "Documents"), os.path.join(home, "OneDrive", "Documents")):
        d = os.path.join(base, "NinjaTrader 8")
        if os.path.isdir(d):
            return d
    return None


def _evidence(root: str) -> list:
    return [f for f in PC_FILES if os.path.isfile(os.path.join(root, "data", f))]


def _read(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else None
    except Exception:  # noqa: BLE001
        return None


def adopt(root: str = ROOT, how: str = "adopt") -> dict:
    """Write data/pc_identity.json for THIS machine (Windows only). -> the record, or {} when refused. Never raises."""
    if not _IS_NT:
        return {}
    rec = {"v": 1, "fp": fingerprint(), "fpn": node_fingerprint(), "t": int(time.time()), "how": how}
    p = os.path.join(root, "data", "pc_identity.json")
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        from engine import fsutil   # retries on a Windows / OneDrive lock (test_selfheal: no bare os.replace on state files)
        fsutil.replace(tmp, p)
    except Exception:  # noqa: BLE001
        return {}
    _CACHE.clear()
    return rec


def check(root: str = ROOT, env=None) -> tuple:
    """(may_post, why). Cached per root for 60 s. Never raises."""
    env = os.environ if env is None else env
    if FORCE is not None:
        return bool(FORCE), "test FORCE"
    if env.get("LE_NO_POST") == "1":
        return False, "LE_NO_POST=1"
    if env.get("GITHUB_ACTIONS") == "true":
        return True, "GitHub Actions (cloud monitor)"
    c = _CACHE.get(root)
    if c and time.time() - c[0] < 60:
        return c[1]
    res = _check(root)
    _CACHE[root] = (time.time(), res)
    return res


def _check(root: str) -> tuple:
    try:
        if not _IS_NT:
            return False, "not the owner's PC (not Windows: a sandbox / test / dev box)"
        rec = _read(os.path.join(root, "data", "pc_identity.json"))
        fp = fingerprint()
        if rec:
            if rec.get("fp") == fp:
                return True, "the owner's PC"
            if not _machine_guid() and (rec.get("fpn") in (None, node_fingerprint())):
                return True, "the owner's PC (MachineGuid not readable now: matched by name / fail-open)"
            if _owner_profile() and (_evidence(root) or _nt_folder()):
                adopt(root, how="re-adopted: fingerprint changed, owner profile + set-up files here")
                return True, "the owner's PC (fingerprint changed: re-adopted)"
            return False, "data/pc_identity.json is another machine's (a copied bot folder): run `python -m engine.pc_identity --adopt` on the real PC"
        ev = _evidence(root) or (["NinjaTrader folder"] if _nt_folder() else [])
        if ev:                                        # Windows + the bot's own local account files (gitignored, made by START /
            adopt(root, how="first run: " + ("NinjaTrader folder + " if _nt_folder() else "") + ",".join(ev))   # ADD_ACCOUNT)
            return True, "the owner's PC (identity adopted now)"
        return False, "no data/pc_identity.json and none of the bot's account files here (not set up by START / ADD_ACCOUNT)"
    except Exception as e:  # noqa: BLE001
        # red team 2026-11-26: on Windows an unknown error POSTS (a missed alarm costs more than a sandbox's stray line);
        # sandboxes are Linux and never get here
        return bool(_IS_NT), f"identity check failed ({e.__class__.__name__}){': fail-open on Windows' if _IS_NT else ''}"


def local(url) -> bool:
    """A loopback target (a test's fake ntfy / push server): it can reach no real phone channel."""
    try:
        from urllib.parse import urlsplit
        return (urlsplit(str(url or "")).hostname or "") in ("127.0.0.1", "localhost", "::1")
    except Exception:  # noqa: BLE001
        return False


def may_post(kind: str = "post", root: str = ROOT, env=None, log=None, url=None) -> bool:
    """True = send for real. False = dry run: one line per process and kind (stderr, or log). url = the target (loopback = always)."""
    if url is not None and local(url):
        return True
    ok, why = check(root, env)
    if not ok and kind not in _SAID:
        _SAID.add(kind)
        try:
            (log or (lambda t: print(t, file=sys.stderr, flush=True)))(f"[noleak] {kind}: dry run, nothing sent ({why})")
        except Exception:  # noqa: BLE001
            pass
    return ok


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if "--adopt" in a:
        if not _IS_NT:
            print("  [FIX]  not Windows: only the owner's PC adopts an identity")
            return 1
        adopt(how="owner --adopt")
        print("  [OK]   this PC is the bot's PC now (data/pc_identity.json)")
        return 0
    ok, why = check()
    print(f"  [{'OK' if ok else '..'}]   {'posts for real' if ok else 'dry run'}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
