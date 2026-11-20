"""The switch. ON needs the owner to TYPE the phrase START CALLING and a daily cap (1-100); OFF needs nothing and wins at once.

  python -m tools.caller.onoff on [--cap 20] [--public https://...]    (CALLER_ON.bat; asks for the phrase on the keyboard)
  python -m tools.caller.onoff off                                     (CALLER_STOP.bat)
  python -m tools.caller.onoff status
Claude never runs 'on' (CLAUDE.md: the owner types live phrases himself); the phrase is read from the keyboard only, never an argument.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "tools.caller"

from . import config as C  # noqa: E402

PHRASE = "START CALLING"


def _write(st: dict, h=None):
    p = os.path.join(C.state_dir(h), "state.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)


def turn_on(typed: str, cap: int, public: str = "", h=None) -> tuple:
    s = C.settings(h)
    if typed.strip() != PHRASE:
        return False, f"Not started: type exactly {PHRASE}."
    if not C.keys_ready(h):
        return False, "Not started: run CALLER_SETUP.bat first (Twilio + Claude keys)."
    if str(s.get("agency_name", "")).upper().startswith("YOUR") or not s.get("agency_name"):
        return False, "Not started: fill agency/config.json (your agency name, phone, address) first: the AI must say who it calls for."
    hard = int(s["limits"]["daily_cap_max"])
    if not (1 <= int(cap) <= hard):
        return False, f"Not started: the daily cap must be 1 to {hard}."
    st = {"on": True, "since": dt.datetime.now(dt.timezone.utc).isoformat(), "daily_cap": int(cap), "public": public, "mode": "consent_only"}
    _write(st, h)
    if s.get("outbound_enabled") is not True:
        return True, "Caller ON: the AI receptionist answers calls to your agency number. It makes no outbound calls (phase 2). CALLER_STOP.bat turns it off."
    return True, f"Caller ON: answers calls, and calls back only businesses that signed the form: at most {cap} a day, weekdays 9-5 their time."


def turn_off(h=None) -> str:
    st = C.read_json(os.path.join(C.state_dir(h), "state.json"), {}) or {}
    st.update({"on": False, "off_at": dt.datetime.now(dt.timezone.utc).isoformat()})
    _write(st, h)
    return "Caller OFF. No call will start. (A call already talking finishes its goodbye.)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["on", "off", "status"])
    ap.add_argument("--cap", type=int, default=0)
    ap.add_argument("--public", default="")
    a = ap.parse_args(argv)
    if a.what == "off":
        print(turn_off())
        return 0
    if a.what == "status":
        st = C.read_json(os.path.join(C.state_dir(), "state.json"), {}) or {}
        print("Caller is " + ("ON" if st.get("on") else "OFF") + (f", cap {st.get('daily_cap')} a day" if st.get("on") else ""))
        return 0
    s = C.settings()
    cap = a.cap or int(input(f"Daily cap (1-{s['limits']['daily_cap_max']}, Enter = {s['limits']['daily_cap']}): ").strip() or s["limits"]["daily_cap"])
    typed = input(f"Type {PHRASE} to turn the AI assistant on: ")
    ok, msg = turn_on(typed, cap, a.public)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
