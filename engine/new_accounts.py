"""New MFFU account Names in NinjaTrader (2026-10-29, owner: "automatic in a few weeks").

When an eval passes or fails the bot stops and pushes; MFFU then gives the owner a NEW account (the funded account after a
pass, a fresh eval after a fail or a new purchase) with a new Name, and that Name shows up in NinjaTrader. This module
notices it and offers it to the owner; it never assigns, arms or trades anything by itself.

  candidates(folder)   the non-Sim NinjaTrader account Names (LE_BarFeed's accounts.csv rows + outgoing\\*_<Name>_Position.txt,
                       engine/go.nt_names) that no bot uses (engine/go.role_of), the owner did not dismiss, and the bot did
                       not retire (a Name replaced through use()). Sized by balance: ~$50,000 -> Zlarior's slot, ~$25,000 ->
                       ATLAS's / BLITZ's (unknown balance: every slot).
  options              per Name, what a tap does, from the slot's last eval outcome (the Start page's account rows,
                       "eval_status" from the running bot, remembered here so it survives the bot being stopped):
                         the slot's eval PASSED -> "funded:zlarior" / "funded:atlas": the Name joins as that slot's FUNDED
                           account (engine/go.to_funded: funded sizing, the eval kept as history);
                         otherwise (failed, a new purchase) -> "zlarior" / "atlas": the Name is the slot's new eval
                           (engine/go.set_names, its mix-up checks); "blitz" = BLITZ's own 25K (ROLE_SETTERS["blitz"] -> engine/go.set_blitz).
  status(rows)         {"new": [...]} for the Start page's one line ("New account <Name> ($50,000): ...").
  use(name, act)       the owner's tap (PC only, bot stopped). Nothing is armed: the next "Start trading" runs the setup for
                       the Name and asks for the live phrase (the auto-resume opt-in belongs to the old Name).
  dismiss(name)        "Not for the bot": never offered again.
  notices(now)         one phone push per new Name (engine/ops_checks.tick, the 5-minute helper; keys kept in its state).
State: data/new_accounts.json (gitignored): dismissed, retired, used, first_seen, outcomes {Name: passed | failed}.
Read-only toward NinjaTrader; never raises in status / notices.
"""
from __future__ import annotations

import json
import re
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = None                          # None = next to engine/go.CFG (data/new_accounts.json; a test's temp go.CFG keeps it temp)


def _path(path=None) -> str:
    if path:
        return path
    if STATE_PATH:
        return STATE_PATH
    from . import go
    return os.path.join(os.path.dirname(go.CFG), "new_accounts.json")
ROLE_LABEL = {"zlarior": "Zlarior", "atlas": "ATLAS", "blitz": "BLITZ"}
SIZE_SPLIT = 35000.0                       # a balance at / above this is a 50K account, below it a 25K one (= go.slot_problem)
ROLE_SETTERS: dict = {}                    # role -> fn(name) -> {"ok", "say" | "error"} (BLITZ's slot registers its own)


def _set_blitz(name: str) -> dict:
    """BLITZ's own 25K slot (engine/go.set_blitz -> engine/account_c.py): assigns the Name, NOT armed (Sim until the owner arms)."""
    from . import go
    return go.set_blitz(name)


ROLE_SETTERS["blitz"] = _set_blitz


def _load(path: str | None = None) -> dict:
    try:
        with open(_path(path), encoding="utf-8") as fh:
            s = json.load(fh)
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def _save(s: dict, path: str | None = None):
    p = _path(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=1)
    from .fsutil import replace as _fs_replace
    _fs_replace(tmp, p)


def fits(balance) -> list:
    """Slots a balance fits: 50K-sized -> Zlarior; 25K-sized -> ATLAS, BLITZ; unknown -> all three."""
    try:
        b = float(balance)
    except (TypeError, ValueError):
        return ["zlarior", "atlas", "blitz"]
    return ["zlarior"] if b >= SIZE_SPLIT else ["atlas", "blitz"]


def remember(rows, path: str | None = None) -> dict:
    """Keep the last eval outcome of each slot's account (rows = engine/go.accounts()["rows"], "eval_status" from the
    running bot): {Name: "passed" | "failed"}. Returns the outcomes known now."""
    s = _load(path)
    out = dict(s.get("outcomes") or {})
    for r in rows or []:
        st = str(r.get("eval_status") or "").lower()
        n = str(r.get("name") or "").strip()
        if n and r.get("state") == "eval" and st in ("passed", "failed"):
            out[n] = st
    if out != (s.get("outcomes") or {}):
        try:
            _save({**s, "outcomes": out}, path)
        except Exception:
            pass
    return out


def options(c: dict, outcomes: dict, lit: str = "", atlas: str = "") -> list:
    """[{"act", "label"}] for one candidate."""
    out = []
    for role in c["roles"]:
        if role == "zlarior":
            if outcomes.get(lit) == "passed":
                out.append({"act": "funded:zlarior", "label": "Use as Zlarior's funded account"})
            else:
                out.append({"act": "zlarior", "label": "Use for Zlarior (new eval)"})
        elif role == "atlas":
            if outcomes.get(atlas) == "passed":
                out.append({"act": "funded:atlas", "label": "Use as ATLAS's funded account"})
            else:
                out.append({"act": "atlas", "label": "Use for ATLAS (new eval)"})
        elif role == "blitz" and "blitz" in ROLE_SETTERS:
            out.append({"act": "blitz", "label": "Use for BLITZ"})
    return out


_ACCT_RE = re.compile(r"OnConnectionStatus: account='([^']+)'")


def log_names(folder: str | None = None) -> list:
    """Account Names NinjaTrader's own trace / log lists when a connection comes up ("Cbi.Account.OnConnectionStatus:
    account='MFFUEVBLDR…6016' ..." for every account of the connection, at each start / reconnect): a new MFFU account
    shows up here even before it has a position file or a balance row. Sim / Playback accounts left out. Never raises."""
    try:
        from . import nt_log
        from .ninjatrader import default_folder, is_sim
        folder = folder or default_folder()
        out = []
        for sub in ("trace", "log"):
            for f in nt_log.files(folder, n=2, sub=sub):
                for n in _ACCT_RE.findall(nt_log._tail(f)):
                    n = n.strip()
                    if n and not is_sim(n) and n not in out:
                        out.append(n)
        return out
    except Exception:
        return []


def candidates(folder: str | None = None, path: str | None = None, names=None, role_of=None, now=None) -> list:
    """[{"name", "balance", "src", "roles", "first_seen"}] of NinjaTrader Names no bot uses yet."""
    from . import go
    s = _load(path)
    if names is None:
        names = list(go.nt_names(folder))
        have = {str(r.get("name") or "").strip() for r in names}
        names += [{"name": n, "balance": None, "src": "NinjaTrader connection log"} for n in log_names(folder) if n not in have]
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


def _say(c: dict, opts: list) -> str:
    bal = f" (${float(c['balance']):,.0f})" if c.get("balance") is not None else ""
    if any(o["act"].startswith("funded:") for o in opts):
        return f"New account {c['name']}{bal} in NinjaTrader: the funded account after the pass?"
    roles = " / ".join(ROLE_LABEL[r] for r in c["roles"] if r != "blitz" or "blitz" in ROLE_SETTERS)
    return f"New account {c['name']}{bal} in NinjaTrader: use it for {roles}?"


def status(folder: str | None = None, path: str | None = None, rows=None, **kw) -> dict:
    """The Start page's block: {"new": [{"name", "balance", "roles", "options", "say"}]}. Never raises."""
    try:
        from . import go
        outcomes = remember(rows, path) if rows is not None else dict(_load(path).get("outcomes") or {})
        lit, atlas = go._names()
        out = []
        for c in candidates(folder, path, **kw):
            o = options(c, outcomes, lit, atlas)
            out.append({**c, "options": o, "say": _say(c, o)})
        return {"new": out, "blitz_ready": "blitz" in ROLE_SETTERS}
    except Exception as e:
        return {"new": [], "error": f"{e.__class__.__name__}"}


def use(name: str, act: str, path: str | None = None, folder: str | None = None, start: str | None = None) -> dict:
    """The owner's tap. act: zlarior | atlas | blitz (a new eval on that slot) or funded:zlarior | funded:atlas (the slot's
    funded account after its pass, engine/go.to_funded, from the next session). Assigns the Name only: never arms."""
    from . import go
    name, act = str(name or "").strip(), str(act or "").strip().lower()
    funded = act.startswith("funded:")
    role = act.split(":", 1)[1] if funded else act
    if role not in ROLE_LABEL or (funded and role == "blitz"):
        return {"ok": False, "error": "Pick Zlarior, ATLAS or BLITZ."}
    if not name:
        return {"ok": False, "error": "No account name."}
    names = {str(r.get("name") or "").strip(): r for r in go.nt_names(folder)}
    for n in log_names(folder):
        names.setdefault(n, {"name": n, "balance": None, "src": "NinjaTrader connection log"})
    if name not in names:
        return {"ok": False, "error": f"NinjaTrader does not show {name}: open NinjaTrader (Accounts tab) and try again."}
    if role not in fits(names[name].get("balance")):
        return {"ok": False, "error": f"{name} looks like a {'50K' if role in ('atlas', 'blitz') else '25K'}-sized account "
                                      f"(${float(names[name]['balance']):,.0f}); {ROLE_LABEL[role]} trades the "
                                      f"{'50K' if role == 'zlarior' else '25K'}."}
    lit, atlas = go._names()
    old = None
    if funded:
        old = lit if role == "zlarior" else atlas
        if not old:
            return {"ok": False, "error": f"{ROLE_LABEL[role]} has no eval account to switch to funded."}
        r = go.to_funded(old, name, start or go.session_day())
        old = None                          # the passed eval stays listed (its history); not retired
    elif role == "zlarior":
        old = lit
        r = go.set_names(name, atlas) if atlas else {"ok": False, "error": "Set ATLAS's 25K first (Accounts set line)."}
    elif role == "atlas":
        old = atlas
        r = go.set_names(lit, name) if lit else {"ok": False, "error": "Set Zlarior's 50K first (Accounts set line)."}
    else:
        fn = ROLE_SETTERS.get("blitz")
        r = fn(name) if fn else {"ok": False, "error": "BLITZ's account slot is not set up yet on this PC (update first)."}
    if not r.get("ok"):
        return r
    s = _load(path)
    s.setdefault("used", {})[name] = {"act": act, "t": int(time.time()), "replaced": old or None}
    if old and old != name:
        s.setdefault("retired", {})[old] = int(time.time())       # the old Name is never offered back as "new"
    _save(s, path)
    what = f"{ROLE_LABEL[role]}'s funded account" if funded else ROLE_LABEL[role]
    return {**{k: v for k, v in r.items() if k not in ("ok", "say")}, "ok": True,
            "say": f"{what} -> {name}. Nothing is armed: tap Start trading; it runs the setup for the new account and asks "
                   "for the live phrase."}


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
            roles = " or ".join(ROLE_LABEL[r] for r in c["roles"] if r != "blitz" or "blitz" in ROLE_SETTERS)
            out.append(push.text_payload("PC", "ops", f"New MFFU account: {c['name']}",
                                         f"NinjaTrader shows {c['name']}{bal}. Open the Start page and tap Use for {roles}. "
                                         "The bot never trades it before your tap and the live phrase.",
                                         key=f"newacct:{c['name']}", t=now, url="#/start"))
        return out
    except Exception:
        return []
