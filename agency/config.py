"""The owner's ONE settings file: agency/config.json (his agency name, phone, email, postal address, city, trades, prices).

agency/config.example.json is the committed starting point with placeholders ("YOUR AGENCY", "YOUR CITY, ST", a 555-01xx
phone, you@example.com). The first run copies it to agency/config.json, which is gitignored: it stays on the owner's PC,
and an edited tracked file would block the bot's auto-update (engine/autoupdate.py skips on local changes).
Every tool reads its settings through load(); a key missing from the owner's copy falls back to the example's value.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil

from . import HERE

EXAMPLE = os.path.join(HERE, "config.example.json")
OWNER = os.path.join(HERE, "config.json")
PLACEHOLDER = re.compile(r"\bYOUR\b|example\.com|555-01\d\d|\b00000\b")


def _merge(base, over):
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            out[k] = _merge(base.get(k), v) if k in base else v
        return out
    return copy.deepcopy(over) if over is not None else copy.deepcopy(base)


def path() -> str:
    return os.environ.get("AGENCY_CONFIG") or OWNER


def ensure_owner_copy() -> str:
    """Make agency/config.json from the example when it does not exist yet. Returns its path."""
    p = path()
    if not os.path.isfile(p):
        shutil.copyfile(EXAMPLE, p)
    return p


def load(p=None) -> dict:
    with open(EXAMPLE, encoding="utf-8") as fh:
        base = json.load(fh)
    p = p or path()
    owner, err = {}, ""
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8-sig") as fh:
                owner = json.load(fh)
        except ValueError as e:
            err = f"{os.path.basename(p)} is not valid JSON (line {getattr(e, 'lineno', '?')}): using the example values until it is fixed"
    cfg = _merge(base, owner)
    cfg["_path"] = p if os.path.isfile(p) else EXAMPLE
    cfg["_error"] = err
    cfg["_placeholders"] = placeholders(cfg)
    return cfg


def placeholders(cfg: dict) -> list:
    """Dotted names of the agency / search fields still holding a placeholder ('agency.name', 'search.city', ...)."""
    out = []
    for sect in ("agency", "search"):
        for k, v in (cfg.get(sect) or {}).items():
            if isinstance(v, str) and PLACEHOLDER.search(v):
                out.append(f"{sect}.{k}")
    return out


def sender_ready(cfg: dict) -> bool:
    """CAN-SPAM needs a real sender name, email and a valid postal address before any email goes out."""
    ph = set(cfg.get("_placeholders") or placeholders(cfg))
    return not ph & {"agency.name", "agency.your_name", "agency.email", "agency.postal_address"}


def package(cfg: dict, pid: str) -> dict:
    for p in cfg.get("packages") or []:
        if p.get("id") == pid:
            return p
    return (cfg.get("packages") or [{}])[0]
