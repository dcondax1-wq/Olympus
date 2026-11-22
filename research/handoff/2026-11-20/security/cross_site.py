"""CROSS-SITE GUARD for the bot server (day-security 2026-11-20). Copy to engine/cross_site.py (LEAD_WIRES.md W1).

The hole: every POST /api/* route of server.py (live/start, live/stop, live/kill, live/arm, live/golive, push, alerts ...) reads
`await req.json()`, which parses a text/plain body too. A text/plain POST is a "simple" request: a browser sends it to
http://localhost:8766 WITHOUT asking first (no CORS preflight). So any web page open in a browser on the PC (an ad, a link in a
chat) could start the bot on a real account with its own "params", kill it mid-trade or arm Tradovate (the phrase is in the
public repo). A page on a DNS-rebinding domain reaches it with Host = that domain. Chrome / Edge now show a "local network
access" prompt for public -> localhost requests; Firefox and older browsers do not.

The rule (pure, no I/O): a state-changing request (not GET / HEAD / OPTIONS) is refused when
  1. Sec-Fetch-Site is "cross-site" or "same-site" (a browser says the request came from another site), or
  2. Origin is present and is not this server (Origin "null" = a sandboxed / file page: refused), or
  3. the Host header is a NAME that is not localhost, the owner's Tailscale name (*.ts.net) or one in LE_ALLOWED_HOSTS
     (DNS rebinding always uses a name; a bare IP such as 192.168.1.20:8766 or 100.x.y.z is fine).
Allowed as before: the PC's own pages (same origin), the phone on the Tailscale link (Host *.ts.net, same origin), scripts and
curl on the PC (no Origin, no Sec-Fetch-Site), the TradingView webhooks (EXEMPT: they carry their own key). Cloud mode
(LE_CLOUD=1) is skipped: it has its own password gate (engine/cloud_guard.py).
"""
from __future__ import annotations

import ipaddress
import os
import urllib.parse

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
LOCAL_NAMES = ("localhost", "127.0.0.1", "::1")
EXEMPT = ("/api/tv/hook", "/api/tv/webhook")


def _hostname(v) -> str:
    v = str(v or "").strip().lower()
    if v.startswith("["):
        return v[1:].split("]", 1)[0]
    return v.rsplit(":", 1)[0] if v.count(":") == 1 else v


def _is_ip(h: str) -> bool:
    try:
        ipaddress.ip_address(h.strip("[]"))
        return True
    except ValueError:
        return False


def host_ok(host: str, env=None) -> bool:
    env = os.environ if env is None else env
    h = _hostname(host)
    if not h:
        return False
    extra = {x.strip().lower() for x in str(env.get("LE_ALLOWED_HOSTS") or "").split(",") if x.strip()}
    return h in LOCAL_NAMES or _is_ip(h) or h.endswith(".ts.net") or h in extra


def why(method: str, path: str, headers, env=None) -> str | None:
    """None = let it through; else the plain reason it was refused."""
    env = os.environ if env is None else env
    if str(method or "").upper() in SAFE_METHODS or env.get("LE_CLOUD") == "1" or env.get("LE_CROSS_SITE_GUARD") == "0":
        return None
    if str(path or "").startswith(EXEMPT):
        return None
    h = {str(k).lower(): str(v) for k, v in (headers.items() if hasattr(headers, "items") else headers or [])}
    host = h.get("host", "")
    sfs = h.get("sec-fetch-site", "").strip().lower()
    if sfs in ("cross-site", "same-site"):
        return "refused: sent by another web site"
    o = h.get("origin", "").strip()
    if o:
        if o.lower() == "null":
            return "refused: sent by a page with no origin"
        if urllib.parse.urlsplit(o).netloc.lower() != host.strip().lower():
            return "refused: sent by another web site"
    if not host_ok(host, env):
        return "refused: unknown host name (open the bot at http://localhost:8766 or your Tailscale link)"
    return None


def install(app):
    """server.py: from engine import cross_site as _xs; _xs.install(app)   (right after the CLOUD GUARD block)."""
    from starlette.responses import JSONResponse

    @app.middleware("http")
    async def cross_site_guard(request, call_next):
        w = why(request.method, request.url.path, request.headers)
        if w:
            return JSONResponse({"ok": False, "error": w}, status_code=403)
        return await call_next(request)
    return app
