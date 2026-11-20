"""Settings, the private home folder, and the keys file (read only here, never printed, never logged).

home    = OLYMPUS_HOME or %USERPROFILE%\\.olympus        (outside the repo)
keys    = <home>/caller.json   {"twilio_sid", "twilio_token", "twilio_from", "anthropic_key"}   written by setup_keys.py (getpass)
state   = <home>/caller/       state.json (on/off, cap), calls.jsonl, consent.jsonl, dnc.txt, registry/<area>.txt,
          share/ (what the PC pushes to the private agency-inbox branch: outbox/<id>.json, consent/<id>.json, status/<lead_id>.json)
"""
from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SECRET_KEYS = ("twilio_sid", "twilio_token", "twilio_from", "anthropic_key", "cf_account", "cf_kv_namespace", "cf_kv_token")


def home() -> str:
    h = os.environ.get("OLYMPUS_HOME") or os.path.join(os.path.expanduser("~"), ".olympus")
    return h


def state_dir(h: str | None = None) -> str:
    d = os.path.join(h or home(), "caller")
    os.makedirs(d, exist_ok=True)
    return d


def read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def settings(h: str | None = None) -> dict:
    """The repo defaults, overridden key by key by <home>/caller/settings.json (the owner's own names, slots, payment link)."""
    base = read_json(os.path.join(HERE, "settings.json"), {}) or {}
    mine = read_json(os.path.join(h or home(), "caller", "settings.json"), {}) or {}
    out = dict(base)
    for k, v in mine.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    out.pop("_read_me", None)
    ag = (read_json(os.path.join(ROOT, "agency", "config.json"), {}) or {}).get("agency") or {}     # the owner's agency file, if filled
    for mine_key, theirs in (("agency_name", "name"), ("callback_number", "phone"), ("postal_address", "postal_address"),
                             ("owner_first_name", "your_name")):
        v = str(ag.get(theirs) or "")
        if v and not v.upper().startswith("YOUR") and str(out.get(mine_key, "")).upper().startswith(("YOUR", "(555)", "THE OWNER")):
            out[mine_key] = v.split()[0] if mine_key == "owner_first_name" else v
    return out


def keys_path(h: str | None = None) -> str:
    return os.path.join(h or home(), "caller.json")


def load_keys(h: str | None = None) -> dict:
    """The secrets, or {} when CALLER_SETUP.bat has not run. Callers must never print or log what this returns."""
    j = read_json(keys_path(h), {}) or {}
    return {k: str(j.get(k) or "") for k in SECRET_KEYS}


def keys_ready(h: str | None = None) -> bool:
    k = load_keys(h)
    return bool(k["twilio_sid"] and k["twilio_token"] and k["twilio_from"] and k["anthropic_key"])


_SECRETISH = [
    re.compile(r"\bAC[0-9a-fA-F]{32}\b"),            # Twilio account SID
    re.compile(r"\bSK[0-9a-fA-F]{32}\b"),            # Twilio API key SID
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{10,}"),     # Anthropic key
    re.compile(r"\b[0-9a-f]{32}\b"),                 # a bare 32-hex token (Twilio auth token)
]


def redact(text: str, h: str | None = None) -> str:
    """Remove every key value and every key-shaped string from a line before it is logged or written."""
    s = str(text)
    for v in load_keys(h).values():
        if v and len(v) >= 6:
            s = s.replace(v, "[hidden]")
    for rx in _SECRETISH:
        s = rx.sub("[hidden]", s)
    return s
