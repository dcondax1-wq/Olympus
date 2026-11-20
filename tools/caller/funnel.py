"""CALLER_ON.bat's helper: the public https address (Tailscale Funnel :10000 -> 127.0.0.1:8790) and the Twilio inbound hook.

  python -m tools.caller.funnel address      prints https://<this-pc>.<tailnet>.ts.net:10000  (from `tailscale status --json`)
  python -m tools.caller.funnel hook URL     sets the agency number's incoming-call webhook to URL/voice/inbound
Funnel is public on purpose (Twilio must reach it): only the caller's port, and every /voice request needs Twilio's signature.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "tools.caller"

from . import config as C  # noqa: E402
from . import telephony as T  # noqa: E402

PORT = 10000


def tailscale() -> str:
    return shutil.which("tailscale") or os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Tailscale", "tailscale.exe")


def address() -> str:
    try:
        out = subprocess.run([tailscale(), "status", "--json"], capture_output=True, text=True, timeout=20).stdout
        name = str((json.loads(out).get("Self") or {}).get("DNSName") or "").rstrip(".")
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""
    return f"https://{name}:{PORT}" if name else ""


def main(argv=None) -> int:
    a = (argv if argv is not None else sys.argv[1:]) or ["address"]
    if a[0] == "address":
        u = address()
        print(u)
        return 0 if u else 1
    if a[0] == "hook" and len(a) > 1:
        ok = T.TwilioAdapter(C.load_keys()).set_voice_url(a[1].rstrip("/") + "/voice/inbound")
        print("[OK] Incoming calls to your Twilio number now reach the AI assistant." if ok else "[FIX] Twilio number not found on this account.")
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
