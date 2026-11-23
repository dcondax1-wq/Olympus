"""What START said about each account, in plain words (2026-11-22, ARM fixer).

Tonight ATLAS ended a START "armed: false" and nothing flagged it: engine/go.step_arm printed one line in the middle of a long
window. This module is the loud end of every START (START_BOT.bat window and the Start page job):

    ARMED: Zlarior 50K
    NOT ARMED: ATLAS 25K: the saved name X is not in NinjaTrader -> type YES at the switch question

plus a banner "Not trading: ..." when ANY real account is not armed. It also keeps data/arm_status.json (gitignored, tiny) so
the phone's glance can say "ATLAS is NOT armed: <reason>" instead of a bare flag (engine/brain_glance.py).

And the one safe repair for the eval -> funded rename: MFFU renames the NinjaTrader account when an eval passes (MFFUEV... ->
MFFUSF..., same last digits). find_funded_candidates() finds the new name; engine/go.py shows both and the owner types YES.
Nothing here arms anything, writes a name or types the phrase: it only reads names and prints / stores text."""
import json
import os
import re
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "arm_status.json")
MAX_AGE_S = 36 * 3600          # a status older than this says nothing about now
_NAME = re.compile(r"^MFFU(EV|SF)(.+)$", re.I)


def parts(name) -> tuple:
    """(stage "EV"/"SF"/None, plan family letters, last 4 digits) of an MFFU NinjaTrader name; family = letters after the stage."""
    n = str(name or "").strip().replace(" ", "")
    m = _NAME.match(n)
    if not m:
        return None, "", ""
    rest = m.group(2)
    digits = re.search(r"(\d+)$", rest)
    return m.group(1).upper(), re.sub(r"[^A-Za-z]", "", rest).upper(), (digits.group(1)[-4:] if digits else "")


def renamed(old, new) -> bool:
    """True when `new` looks like the funded name of the passed eval `old`: eval stage -> funded stage, same plan family,
    same last 4 digits."""
    so, fo, lo = parts(old)
    sn, fn, ln = parts(new)
    return so == "EV" and sn == "SF" and bool(fo) and fo == fn and bool(lo) and lo == ln


def find_funded_candidates(old, nt_names, taken=None) -> list:
    """The NinjaTrader accounts that could be `old`'s funded rename. `taken(name)` -> True for a name another bot already
    trades (never offered). Sim accounts never match (their names carry no MFFU stage)."""
    out = []
    for n in nt_names or []:
        n = str(n or "").strip()
        if n and n != str(old or "").strip() and renamed(old, n) and not (taken and taken(n)) and n not in out:
            out.append(n)
    return out


_ID = re.compile(r"[A-Za-z]*\d[A-Za-z0-9_]{4,}")


def mask(text) -> str:
    """Account Names / ids -> their last 4 ('MFFUSFBLDR000006018' -> '...6018'): the glance rides in the PUBLIC status post
    (red team 2026-11-23: a START reason quotes NinjaTrader's full Names)."""
    def m(x):
        w = x.group(0)
        return "..." + w[-4:] if sum(ch.isdigit() for ch in w) >= 3 else w
    return _ID.sub(m, str(text or ""))


def row(label, armed, reason="", fix="") -> dict:
    return {"label": label, "armed": bool(armed), "reason": str(reason or "")[:200], "fix": str(fix or "")[:200]}


def lines(rows) -> list:
    """One line per account, then the banner when any real account is not armed."""
    out = [(f"ARMED: {r['label']}" if r["armed"] else
            f"NOT ARMED: {r['label']}: {r['reason'] or 'not armed'} -> {r['fix'] or 'send Claude a photo of this window'}")
           for r in rows]
    bad = [r["label"] for r in rows if not r["armed"]]
    if bad:
        bar = "=" * 64
        out += ["", bar, f" NOT TRADING: {', '.join(bad)}", "   (these accounts will not take a trade until the fix above is done)", bar]
    return out


def save(rows, path=None, now=None) -> None:
    """data/arm_status.json: {"t", "rows": [{key, label, armed, reason}]}. Never raises."""
    path = path or PATH
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"t": int(now if now is not None else time.time()), "rows": rows}, fh)
        os.replace(tmp, path)
    except Exception:  # noqa: BLE001
        pass


def glance_reason(key, path=None, now=None) -> str | None:
    """The phone's plain line for a bot that the last START did not arm ("ATLAS is NOT armed: <reason>"), else None.
    `key` is the account's label start ("Zlarior" / "ATLAS"). Never raises; a status older than 36 h is ignored."""
    try:
        with open(path or PATH, encoding="utf-8") as fh:
            d = json.load(fh)
        if (now if now is not None else time.time()) - float(d.get("t") or 0) > MAX_AGE_S:
            return None
        for r in d.get("rows") or []:
            if str(r.get("label") or "").lower().startswith(str(key).lower()) and r.get("armed") is False:
                return f"{r['label'].split(' ')[0]} is NOT armed: {mask(str(r.get('reason') or 'see the Start page'))[:90]}"[:110]
    except Exception:  # noqa: BLE001
        pass
    return None
