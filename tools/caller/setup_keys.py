"""CALLER_SETUP.bat: asks for the Twilio and Claude keys with getpass (nothing shows as you paste) and saves them ONLY in
%USERPROFILE%\\.olympus\\caller.json (outside the repo). It never prints a key; it prints the last 4 characters of the phone number only.
"""
from __future__ import annotations

import getpass
import json
import os
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "tools.caller"

from . import config as C  # noqa: E402
from . import compliance as G  # noqa: E402


def save(keys: dict, h=None) -> str:
    p = C.keys_path(h)
    root = os.path.realpath(C.ROOT)
    if os.path.realpath(p).startswith(root + os.sep):
        raise SystemExit("refusing to save keys inside the repo")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    old = C.read_json(p, {}) or {}
    old.update({k: v for k, v in keys.items() if v})
    with open(p, "w", encoding="utf-8") as f:
        json.dump(old, f)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p


def main(ask=getpass.getpass) -> int:
    print("AI caller keys (Enter keeps the one already saved). Nothing you paste is shown.")
    sid = ask("1/4 Twilio Account SID (starts with AC): ").strip()
    tok = ask("2/4 Twilio Auth Token: ").strip()
    frm = ask("3/4 Your Twilio phone number (+1...): ").strip()
    ant = ask("4/4 Claude API key (starts with sk-ant-): ").strip()
    if sid and not re.fullmatch(r"AC[0-9a-fA-F]{32}", sid):
        print("[FIX] That SID does not look right (AC + 32 letters/numbers). Nothing saved.")
        return 1
    if frm and not G.e164(frm):
        print("[FIX] That phone number does not look like +1 and 10 digits. Nothing saved.")
        return 1
    p = save({"twilio_sid": sid, "twilio_token": tok, "twilio_from": G.e164(frm) if frm else "", "anthropic_key": ant})
    k = C.load_keys()
    print(f"[OK] Saved in {p} (outside the repo). Number ends ...{k['twilio_from'][-4:] if k['twilio_from'] else '----'}; "
          f"all 4 keys {'present' if C.keys_ready() else 'NOT all present yet'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
