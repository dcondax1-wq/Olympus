"""NinjaScript add-on sync without the editor (day-handsfree 2026-11-25; owner: "I don't want to go on my PC ... every single time").

The problem: ninjatrader/LE_TickRec.cs (the order-flow recorder) ships with the code, but NinjaTrader runs the COMPILED copy of the
file in Documents\\NinjaTrader 8\\bin\\Custom\\AddOns\\. Until today a new version needed the owner at the PC: copy the file
(tools/finish_tonight.py) + NinjaScript Editor + F5.

What is automatic now (self-heal, hourly, engine/self_heal REMEDIES "ninjascript"):
  1. COPY: when the repo's LE_TickRec.cs differs from the AddOns copy (and the AddOns copy exists, i.e. the owner installed the
     recorder once), the new file is copied over it: only outside 01:50-16:00 ET on a weekday and only when no trade may be open
     (NinjaTrader recompiles ALL NinjaScript when it compiles, which reloads the charts' LE_BarFeed for a moment).
  2. COMPILE: NinjaTrader 8 watches its bin\\Custom folder and normally compiles by itself when a .cs file in it changes while it
     runs (the same thing that happens when you save from Visual Studio). Honest status: this is NinjaTrader's documented
     external-editor behaviour, NOT yet seen on the owner's PC; step 3 proves it either way.
  3. PROOF: the add-on writes its build id into its status line (le_ticks\\le_tickrec_status.txt ",v=<LE_BUILD>"). LE_BUILD is
     the first 10 hex of the SHA-256 of the file with the LE_BUILD value blanked (build_id()). A fresh status line with another
     build (or none: a build from before today) 30+ min after the copy = NinjaTrader still runs the old compiled code -> ONE
     alert per new build: "NinjaTrader > New > NinjaScript Editor > F5 (once)". When it matches: nothing to do, nothing sent.
What is NOT possible hands-free: NinjaTrader has no command line / API to compile, and an exported compiled assembly or an import
package (.zip) is imported through its own GUI (Tools > Import), so a click stays possible in the worst case: one alert, once.

  python -m engine.ns_sync --status     what is installed / running vs the repo
  python -m engine.ns_sync --stamp      (Claude, after editing the .cs) write the new LE_BUILD into the file
State: logs/self_heal/ns_sync.json (gitignored). Off: LE_NS_SYNC=0.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ("LE_TickRec.cs",)                       # the add-ons this sync keeps current (LE_BarFeed is a chart indicator: by hand)
BUILD_RX = re.compile(r'(public\s+const\s+string\s+LE_BUILD\s*=\s*")([0-9a-f]*)(")')
STATUS_REL = os.path.join("le_ticks", "le_tickrec_status.txt")
FRESH_S = 5 * 60                                 # the add-on writes its status line every 15 s
COMPILE_WAIT_S = 30 * 60
STATE_REL = os.path.join("logs", "self_heal", "ns_sync.json")
F5_STEP = "NinjaTrader > New > NinjaScript Editor > press F5 once (then close the editor)"


def build_id(text: str) -> str:
    """The build id of a .cs file: SHA-256 of its text (LF line ends) with the LE_BUILD value blanked; first 10 hex."""
    t = str(text or "").replace("\r\n", "\n")
    t = BUILD_RX.sub(r"\1\3", t)
    return hashlib.sha256(t.encode("utf-8")).hexdigest()[:10]


def stamped(text: str) -> str | None:
    m = BUILD_RX.search(str(text or ""))
    return m.group(2) if m else None


def stamp_text(text: str) -> str:
    return BUILD_RX.sub(lambda m: m.group(1) + build_id(text) + m.group(3), text, count=1)


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _in_trading(now) -> bool:
    e = dt.datetime.fromtimestamp(float(now), ET)
    m = e.hour * 60 + e.minute
    return e.weekday() < 5 and 110 <= m < 960


def running_build(nt: str, now=None) -> tuple:
    """(build | "" for a status line without one, fresh?) from the add-on's status line; (None, False) without the file."""
    now = time.time() if now is None else now
    p = os.path.join(nt, STATUS_REL)
    try:
        line = open(p, encoding="utf-8").read().strip()
        age = now - os.path.getmtime(p)
    except OSError:
        return None, False
    v = ""
    for part in line.split(",")[1:]:
        if part.startswith("v="):
            v = part[2:].strip()
    return v, age <= FRESH_S


def _state(root):
    try:
        with open(os.path.join(root, STATE_REL), encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(root, d):
    try:
        p = os.path.join(root, STATE_REL)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        from .fsutil import replace as _replace          # retried: Windows / OneDrive lock the target a moment
        _replace(p + ".tmp", p)
    except OSError:
        pass


def check(root: str, nt: str | None, now=None, apply: bool = True, flat=None) -> list:
    """[{"file", "status": ok | copied | would | wait | need | info | skip, "text"}]. flat: fn() -> None (flat) or why not.
    Never raises."""
    now = time.time() if now is None else float(now)
    out = []
    if not nt or not os.path.isdir(nt):
        return out
    st = _state(root)
    for name in FILES:
        try:
            out.append(_one(root, nt, name, now, apply, flat, st))
        except Exception as e:  # noqa: BLE001
            out.append({"file": name, "status": "info", "text": f"{name}: check failed ({e.__class__.__name__})"})
    if apply:
        _save(root, st)
    return out


def _one(root, nt, name, now, apply, flat, st) -> dict:
    src = os.path.join(root, "ninjatrader", name)
    dst = os.path.join(nt, "bin", "Custom", "AddOns", name)
    repo = _read(src)
    if repo is None:
        return {"file": name, "status": "skip", "text": f"{name} not in the bot folder"}
    want = build_id(repo)
    have = _read(dst)
    if have is None:
        return {"file": name, "status": "skip", "text": f"{name} is not installed in NinjaTrader (optional: tools/finish_tonight.py)"}
    rec = st.setdefault(name, {})
    if build_id(have) != want:
        if _in_trading(now):
            return {"file": name, "status": "wait", "text": f"new {name} waits for 16:00 ET (never copied during trading hours)"}
        why = flat() if callable(flat) else None
        if why:
            return {"file": name, "status": "wait", "text": f"new {name} waits: {why}"}
        if not apply:
            return {"file": name, "status": "would", "text": f"would copy the new {name} ({want}) into NinjaTrader's AddOns"}
        tmp = dst + ".le_new"
        shutil.copyfile(src, tmp)
        from .fsutil import replace as _replace
        _replace(tmp, dst)
        rec.update(copied=int(now), build=want)
        return {"file": name, "status": "copied", "text": f"copied the new {name} ({want}) into NinjaTrader (it compiles by itself)"}
    run, fresh = running_build(nt, now)
    if run is None or not fresh:
        return {"file": name, "status": "info", "text": f"{name} {want} installed; NinjaTrader is not running it right now"}
    if run == want:
        if rec.get("need") == want:
            rec["ok"] = int(now)
        return {"file": name, "status": "ok", "text": f"NinjaTrader runs {name} {want}"}
    since = float(rec.get("copied") or 0) if rec.get("build") == want else 0.0
    if since and now - since < COMPILE_WAIT_S:
        return {"file": name, "status": "wait", "text": f"{name} {want} copied {int((now - since) // 60)} min ago: waiting for "
                                                       "NinjaTrader to compile it"}
    if rec.get("need") == want:
        return {"file": name, "status": "info", "text": f"NinjaTrader still runs the old {name} ({run or 'before build ids'}): {F5_STEP}"}
    if apply:
        rec["need"] = want
    return {"file": name, "status": "need", "text": f"NinjaTrader still runs the old {name} ({run or 'before build ids'}; new = {want}). "
                                                   f"Once: {F5_STEP}", "step": F5_STEP}


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if "--stamp" in a:
        for name in FILES:
            p = os.path.join(ROOT, "ninjatrader", name)
            t = _read(p)
            if t is None or not BUILD_RX.search(t):
                print(f"{name}: no LE_BUILD line")
                continue
            new = stamp_text(t)
            with open(p, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
            print(f"{name}: LE_BUILD = {stamped(new)}")
        return 0
    from .tickrec import nt_dir
    for r in check(ROOT, nt_dir(), apply=False):
        print(f"{r['status']:7} {r['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
