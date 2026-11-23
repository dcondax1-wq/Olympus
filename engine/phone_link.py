"""Phone link for the bot server (owner 2026-11-20: "I want to add the account now on my phone, find a way").

The PC's Tailscale https address (https://<pc>.<tailnet>.ts.net/, port 443) can belong to another app on the PC (the owner's
old Jarvis app answered there with its own sign-in), so the bot pages (/add-account/, /safety/, /kalshi-live/) were not on the
phone link at all. At every server start this module makes sure the bot server has its OWN private https port inside the
owner's tailnet:

    https://<pc>.<tailnet>.ts.net:8444/  ->  http://127.0.0.1:8766  (tailnet only, never Funnel)

Rules: Windows PC only (os.name == "nt"), Tailscale installed and signed in, LE_PHONE_LINK != "0". It never touches port 443 or
any port another app uses, never turns Funnel on, and changes nothing when the bot server is already on a private port (any
port, e.g. tools/bat/LIVE_LINK.bat put it on 443). Runs once in a background thread at server start (never blocks the bot, every call
has a timeout). The pages themselves keep their own check (engine/live_site.private_why: tailnet devices only).

Windows notes (review 2026-11-20, Tailscale 1.7x and newer):
  * tailscale.exe: PATH first (the installer adds it), else %ProgramW6432% / %ProgramFiles% + Tailscale/tailscale.exe (a
    32-bit Python sees %ProgramFiles% = "Program Files (x86)", so ProgramW6432 and the fixed "C:/Program Files" too).
  * the command is the serve v2 CLI (1.52+): `tailscale serve --bg --yes --https=8444 http://127.0.0.1:8766`, flags before
    the target. A Tailscale without --yes ("flag provided but not defined") is asked once more without it.
  * output is UTF-8 (status --json carries the tailnet user's display name): read as UTF-8, never the cp1252 console code
    page (a Greek letter there broke the JSON and read as "not signed in"). stdin is closed, so a question from Tailscale
    (turn Serve / HTTPS on for the tailnet) can never wait on the server window; it times out and its login.tailscale.com
    link is passed on in the reason.
  * `tailscale serve status --json` = the ipn.ServeConfig: {"TCP": {"443": {"HTTPS": true}}, "Web": {"<host>:443":
    {"Handlers": {"/": {"Proxy": "http://127.0.0.1:5000"}}}}, "AllowFunnel": {"<host>:443": true}, "Foreground":
    {"<session>": {same shape}}} or null / {} when nothing is served. Foreground sessions (a `tailscale serve` left
    running in a window) count as used ports too.
  * permission: on Windows there is no `--operator` (that is Linux / macOS); the LocalAPI lets the Windows user who is
    signed in to the Tailscale app change serve, without admin (admin is only needed to serve a folder, never done
    here). A server run as ANOTHER Windows user is refused ("in use by" / "Access denied"): the reason says so.
  * at logon the server can start before Tailscale is connected: start_background tries again (every 30 s, ~5 min).
Tests: python -X utf8 -m tests.test_phone_link
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time

PORTS = (8444, 8446, 8448)                      # 443 = whatever the owner set (Jarvis / LIVE_LINK), 8443 = MONEY_INBOX
TARGETS = ("http://127.0.0.1:8766", "http://localhost:8766", "127.0.0.1:8766", "localhost:8766")
TIMEOUT = 20
RETRY_TRIES, RETRY_WAIT_S = 10, 30.0            # at logon: Tailscale may connect a few minutes after the server starts
_URL = re.compile(r"https://login\.tailscale\.com/\S+")


def find_tailscale(env=None) -> str | None:
    env = os.environ if env is None else env
    p = env.get("LE_TAILSCALE")
    if p:
        return p if os.path.isfile(p) else None
    w = shutil.which("tailscale")
    if w:
        return w
    seen = []
    for d in (env.get("ProgramW6432"), env.get("ProgramFiles"), "C:\\Program Files", env.get("ProgramFiles(x86)")):
        if d and d not in seen:
            seen.append(d)
            c = os.path.join(d, "Tailscale", "tailscale.exe")
            if os.path.isfile(c):
                return c
    return None


class _Out:
    def __init__(self, returncode, stdout, stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _default_runner(cmd):
    """UTF-8 (not the console code page), stdin closed (a question never waits), no console window, a hard timeout.
    A timeout comes back as returncode -9 with what Tailscale printed so far (its login link, if it asked one)."""
    kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {}
    try:
        return subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8",
                              errors="replace", timeout=TIMEOUT, **kw)
    except subprocess.TimeoutExpired as e:
        out = e.stdout or e.output or ""
        out = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
        err = e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return _Out(-9, out, err + "\n(timed out after %d s)" % TIMEOUT)


def _run(ts, args, runner=None):
    return (runner or _default_runner)([ts] + list(args))


def _json(ts, args, runner=None) -> dict:
    """The command's JSON as a dict; {} for no output, "null" (nothing served), bad JSON or a failure."""
    try:
        r = _run(ts, args, runner)
        out = (getattr(r, "stdout", "") or "").strip()
        d = json.loads(out) if out else {}
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _said(r) -> str:
    """What Tailscale answered, in one short line (stderr first)."""
    t = " ".join(str(getattr(r, k, "") or "") for k in ("stderr", "stdout")).strip()
    return " ".join(t.split())[:300]


def refusal(r) -> str:
    """A plain reason from a failed `tailscale serve` answer."""
    t = _said(r)
    low = t.lower()
    url = _URL.search(t)
    if url:
        return ("Tailscale asks you to switch Serve / HTTPS on for your tailnet: open %s once (signed in), then restart "
                "the bot" % url.group(0).rstrip(".,)"))
    if "in use by" in low or "access denied" in low or "denied" in low or "permission" in low:
        return ("Tailscale refused (%s): run the bot as the Windows user who is signed in to the Tailscale app" % t[:120])
    if "timed out" in low:
        return "Tailscale did not answer in %d s (is the Tailscale app running?)" % TIMEOUT
    return "Tailscale did not take it (%s)" % (t[:160] or "HTTPS certificates off in the tailnet?")


def _ours(proxy) -> bool:
    p = str(proxy or "").strip().rstrip("/").lower()
    return any(p == t for t in TARGETS)


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def scan(serve: dict) -> dict:
    """{'ours': [port...] (bot server, Funnel off), 'funnel': [port...] (bot server but Funnel on), 'used': {port...}}.
    A foreground session's ports (serve.Foreground) are 'used' but never 'ours': they end when that window closes."""
    serve = _d(serve)
    used = set()
    ours, fun = set(), set()
    fg = [_d(v) for v in _d(serve.get("Foreground")).values()]
    for i, cfg in enumerate([serve] + fg):
        used |= {int(k) for k in _d(cfg.get("TCP")) if str(k).isdigit()}
        funnel = {str(k).lower() for k, v in _d(cfg.get("AllowFunnel")).items() if v}
        for hostport, web in _d(cfg.get("Web")).items():
            hp = str(hostport)
            port = int(hp.rsplit(":", 1)[1]) if ":" in hp and hp.rsplit(":", 1)[1].isdigit() else 443
            handlers = _d(_d(web).get("Handlers"))
            if i == 0 and any(_ours(_d(h).get("Proxy")) for h in handlers.values()):
                (fun if hp.lower() in funnel else ours).add(port)
            used.add(port)
    return {"ours": sorted(ours), "funnel": sorted(fun), "used": used}


def ensure(env=None, runner=None, ts=None, say=print) -> dict:
    """Make sure the bot server is on a private Tailscale https port. Returns {'ok', 'port', 'why'}. Never raises."""
    env = os.environ if env is None else env
    try:
        if str(env.get("LE_PHONE_LINK", "1")) == "0":
            return {"ok": False, "port": None, "why": "off (LE_PHONE_LINK=0)"}
        ts = ts or find_tailscale(env)
        if not ts:
            return {"ok": False, "port": None, "why": "Tailscale is not installed on this PC"}
        st = _json(ts, ["status", "--json"], runner)
        if str(st.get("BackendState", "")) != "Running":
            return {"ok": False, "port": None, "why": "Tailscale is not signed in / running"}
        s = scan(_json(ts, ["serve", "status", "--json"], runner))
        if s["ours"]:
            return {"ok": True, "port": s["ours"][0], "why": "already on"}
        port = next((p for p in PORTS if p not in s["used"]), None)
        if port is None:
            return {"ok": False, "port": None, "why": "no free port among %s" % (PORTS,)}
        cmd = ["serve", "--bg", "--yes", "--https=%d" % port, TARGETS[0]]
        r = _run(ts, cmd, runner)
        if getattr(r, "returncode", 0) and "not defined: -yes" in _said(r):     # a Tailscale without --yes
            r = _run(ts, [a for a in cmd if a != "--yes"], runner)
        s2 = scan(_json(ts, ["serve", "status", "--json"], runner))
        if port in s2["ours"]:
            say("[phone_link] bot server on your private Tailscale link, port %d (tailnet only, Funnel off)" % port)
            return {"ok": True, "port": port, "why": "switched on"}
        if not getattr(r, "returncode", 0):
            return {"ok": False, "port": None, "why": "Tailscale did not take it (HTTPS certificates off in the tailnet?)"}
        return {"ok": False, "port": None, "why": refusal(r)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "port": None, "why": "%s: %s" % (e.__class__.__name__, e)}


def _retry(why) -> bool:
    """Worth another try a little later (Tailscale still connecting at logon / not answering yet)."""
    w = str(why or "")
    return w.startswith("Tailscale is not signed in") or "did not answer" in w


def start_background(env=None, say=print, tries: int = RETRY_TRIES, wait_s: float = RETRY_WAIT_S, sleep=time.sleep,
                     force: bool = False) -> threading.Thread | None:
    """Server start hook: Windows only, in a daemon thread, never blocks or breaks the bot. When Tailscale is not
    connected yet (the PC just logged on), it tries again every wait_s, up to `tries` times. force: tests only."""
    env = os.environ if env is None else env
    if (os.name != "nt" and not force) or str(env.get("LE_PHONE_LINK", "1")) == "0" or env.get("LE_CLOUD"):
        return None

    def _go():
        r = ensure(env=env, say=say)
        n = 1
        while not r.get("ok") and _retry(r.get("why")) and n < max(1, int(tries)):
            sleep(wait_s)
            r = ensure(env=env, say=say)
            n += 1
        say("[phone_link] %s" % ("port %s: %s" % (r["port"], r["why"]) if r.get("ok") else "not on: " + str(r.get("why"))))

    t = threading.Thread(target=_go, name="phone_link", daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    print(ensure())
