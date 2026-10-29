"""New MFFU account Names in NinjaTrader (2026-10-29, owner: "automatic in a few weeks").

When an eval passes or fails the bot stops and pushes; MFFU then gives the owner a NEW account (the funded account after a
pass, a fresh eval after a fail or a new purchase) with a new Name, and that Name shows up in NinjaTrader. This module
notices it and offers it to the owner; it never assigns, arms or trades anything by itself.

  candidates(folder)   the non-Sim NinjaTrader account Names (LE_BarFeed's accounts.csv rows + outgoing\\*_<Name>_Position.txt,
                       engine/go.nt_names) that no bot uses (engine/go.role_of), the owner did not dismiss, and the bot did
                       not retire (a Name replaced through use()). Each with its balance (when fresh) and the roles that fit
                       its size: ~$50,000 -> Zlarior; ~$25,000 -> ATLAS / BLITZ.
  status(folder)       {"new": [...]} for the Start page's one line ("New account <Name> ($50,000): Use for Zlarior ...").
  use(name, role)      the owner's tap: Zlarior -> the 50K Name (engine/go.set_names, its mix-up checks; the bot must be
                       stopped), ATLAS -> the 25K Name, BLITZ -> the hook another part registers (ROLE_SETTERS["blitz"]).
                       Nothing is armed: the next "Start trading" runs the setup for the new Name and asks for the live phrase
                       (the auto-resume opt-in belongs to the old Name), as for any new account.
  dismiss(name)        "Not for the bot": never offered again.
  notices(state, now)  one phone push per new Name (engine/ops_checks.tick, the 5-minute helper; keys kept in its state).
State: data/new_accounts.json (gitignored): {"dismissed": [...], "retired": {name: t}, "used": {name: {role, t, replaced}},
"first_seen": {name: t}}. Read-only toward NinjaTrader; never raises in status / notices.
"""
from __future__ import annotations

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "new_accounts.json")
ROLE_LABEL = {"zlarior": "Zlarior", "atlas": "ATLAS", "blitz": "BLITZ"}
SIZE_SPLIT = 40000.0                       # a balance at / above this is a 50K account, below it a 25K one
ROLE_SETTERS: dict = {}                    # role -> fn(name) -> {"ok", "say" | "error"} (BLITZ's slot registers its own)


def _load(path: str | None = None) -> dict:
    try:
        with open(path or STATE_PATH, encoding="utf-8") as fh:
            s = json.load(fh)
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def _save(s: dict, path: str | None = None):
    p = path or STATE_PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=1)
    from .fsutil import replace as _fs_replace
    _fs_replace(tmp, p)


def fits(balance) -> list:
    """Roles a balance fits: 50K-sized -> Zlarior; 25K-sized -> ATLAS, BLITZ; unknown -> all three."""
    try:
        b = float(balance)
    except (TypeError, ValueError):
        return ["zlarior", "atlas", "blitz"]
    return ["zlarior"] if b >= SIZE_SPLIT else ["atlas", "blitz"]


def candidates(folder: str | None = None, path: str | None = None, names=None, role_of=None, now=None) -> list:
    """[{"name", "balance", "src", "roles", "first_seen"}] of NinjaTrader Names no bot uses yet."""
    from . import go
    s = _load(path)
    names = go.nt_names(folder) if names is None else names
    role_of = role_of or go.role_of
    skip = set(s.get("dismissed") or []) | set((s.get("retired") or {}).keys())
    out = []
    seen = dict(s.get("first_seen") or {})
    now = int(time.time() if now is None else now)
    for r in names:
        n = str(r.get("name") or "").strip()
        if not n or n in skip or role_of(n):
            continue
        seen.setdefault(n, now)
        out.append({"name": n, "balance": r.get("balance"), "src": r.get("src"), "roles": fits(r.get("balance")),
                    "first_seen": seen[n]})
    if seen != (s.get("first_seen") or {}):
        try:
            _save({**s, "first_seen": seen}, path)
        except Exception:
            pass
    return out


def _say(c: dict) -> str:
    bal = f" (${float(c['balance']):,.0f})" if c.get("balance") is not None else ""
    roles = " / ".join(ROLE_LABEL[r] for r in c["roles"])
    return f"New account {c['name']}{bal} in NinjaTrader: use it for {roles}?"


def status(folder: str | None = None, path: str | None = None, **kw) -> dict:
    """The Start page's block: {"new": [{"name", "balance", "roles", "say"}], "blitz_ready": bool}. Never raises."""
    try:
        rows = candidates(folder, path, **kw)
        return {"new": [{**c, "say": _say(c)} for c in rows], "blitz_ready": "blitz" in ROLE_SETTERS}
    except Exception as e:
        return {"new": [], "error": f"{e.__class__.__name__}"}


def use(name: str, role: str, path: str | None = None, folder: str | None = None) -> dict:
    """The owner's tap "Use <Name> for <role>". Assigns the Name only (never arms, never starts)."""
    from . import go
    name, role = str(name or "").strip(), str(role or "").strip().lower()
    if role not in ROLE_LABEL:
        return {"ok": False, "error": "Pick Zlarior, ATLAS or BLITZ."}
    if not name:
        return {"ok": False, "error": "No account name."}
    names = {str(r.get("name") or "").strip(): r for r in go.nt_names(folder)}
    if name not in names:
        return {"ok": False, "error": f"NinjaTrader does not show {name}: open NinjaTrader (Accounts tab) and try again."}
    if role not in fits(names[name].get("balance")):
        return {"ok": False, "error": f"{name} looks like a {'50K' if role == 'atlas' or role == 'blitz' else '25K'}-sized account "
                                      f"(${float(names[name]['balance']):,.0f}); {ROLE_LABEL[role]} trades the "
                                      f"{'50K' if role == 'zlarior' else '25K'}."}
    lit, atlas = go._names()
    if role == "zlarior":
        old = lit
        r = go.set_names(name, atlas) if atlas else {"ok": False, "error": "Set ATLAS's 25K first (Accounts set line)."}
    elif role == "atlas":
        old = atlas
        r = go.set_names(lit, name) if lit else {"ok": False, "error": "Set Zlarior's 50K first (Accounts set line)."}
    else:
        fn = ROLE_SETTERS.get("blitz")
        old = None
        r = fn(name) if fn else {"ok": False, "error": "BLITZ's account slot is not set up yet on this PC (update first)."}
    if not r.get("ok"):
        return r
    s = _load(path)
    s.setdefault("used", {})[name] = {"role": role, "t": int(time.time()), "replaced": old or None}
    if old and old != name:
        s.setdefault("retired", {})[old] = int(time.time())       # the old Name is never offered back as "new"
    _save(s, path)
    return {**{k: v for k, v in r.items() if k not in ("ok", "say")}, "ok": True,
            "say": f"{ROLE_LABEL[role]} -> {name}. Nothing is armed: tap Start trading; it runs the setup for the new account "
                   "and asks for the live phrase."}


def dismiss(name: str, path: str | None = None) -> dict:
    name = str(name or "").strip()
    if not name:
        return {"ok": False, "error": "No account name."}
    s = _load(path)
    d = s.setdefault("dismissed", [])
    if name not in d:
        d.append(name)
    _save(s, path)
    return {"ok": True, "say": f"{name} is not offered again."}


def notices(now=None, folder: str | None = None, path: str | None = None, **kw) -> list:
    """One push payload per new Name (key newacct:<Name>: engine/ops_checks.send keeps the keys, so each goes once)."""
    try:
        from . import push
        now = int(time.time() if now is None else now)
        out = []
        for c in candidates(folder, path, now=now, **kw):
            bal = f" (${float(c['balance']):,.0f})" if c.get("balance") is not None else ""
            roles = " or ".join(ROLE_LABEL[r] for r in c["roles"])
            out.append(push.text_payload("PC", "ops", f"New MFFU account: {c['name']}",
                                         f"NinjaTrader shows {c['name']}{bal}. Open the Start page and tap Use for {roles}. "
                                         "The bot never trades it before your tap and the live phrase.",
                                         key=f"newacct:{c['name']}", t=now, url="#/start"))
        return out
    except Exception:
        return []
