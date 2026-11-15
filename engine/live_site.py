"""LIVE SITE: the whole phone site, live, from the PC's own bot server (owner 2026-11-12: "I want everything connected. I want an
actual dashboard"). docs/LIVE_DASHBOARD.md. server.py installs it (install(app, live=LIVEPUB.payload)) before its static mount.

The phone reaches the server privately through Tailscale (LIVE_LINK.bat: `tailscale serve` turns https://<pc>.<tailnet>.ts.net/
into a proxy to http://127.0.0.1:8766, inside the owner's tailnet only, never Funnel). Through that one link:

  /                      a request that came through the link (proxy headers) is sent to the Gate: /site/gate/
  /site/...              the built site (tools/pc_publish.py / PUBLISH_NQ.bat or LIVE_LINK's build task, every 15 min): the Gate,
                         the root dashboard, every OLYMPUS app. Newest of data/pc_publish/site and data/live_site/site (LE_SITE_DIR
                         overrides), a missing file falls back to tools/web_public (the same public files, unbuilt).
  /site/home.json        the built home.json with the bot's live numbers laid over it (overlay_home: the Python twin of
                         tools/web_public/pc_feed.js overlayHome), so every app that reads home.json is live, not 15 min old
  /site/kalshi.json      the Kalshi feed fresh from the owner's setting (publish.json "kalshi_file" or "kalshi_feed_url", the same
                         keys tools/pc_publish.add_kalshi reads), else the site's copy, else 404 (the page says so)
  /site/money/<id>.json  the money machines' newest output (money_out/, RUN_MONEY.bat) instead of the build's sample copy
  /site/day/day.json     your day from your own calendars (tools/calendar_sync.py -> data/day/day.json, docs/CONNECT_DAY.md):
                         PRIVATE, so it lives only in data/day/ and only this route serves it (never a site folder, never
                         PUBLISH_NQ / Netlify / GitHub Pages); 404 with a plain reason until a calendar is connected
                         (+ money/household.json: your bank exports' summary, tools/money_import.py; on this link only)
  /site/me/<file>.json   the Me hub (hub/?h=me, docs/ME_HUB.md): me.json (tools/me_hub.py: money, cards, health, home, dates),
                         health.json (tools/me_health.py: the Apple Watch Shortcut + the Health export), home.json (tools/me_home.py:
                         WiFi speed, outages, devices, this PC). PRIVATE like day/: only data/me/ (LE_ME_DIR), only this route,
                         never a site folder, never PUBLISH_NQ / Netlify / GitHub Pages; 404 with a plain reason until it is made
  GET /api/site/live.json  the bot's live.json (engine/live_publish.build of the running bot: kind "le-live", pc, pc_verdict,
                         board, accounts), at most 15 s old; the Gate's "Right now" card reads it
  GET /api/site/status   what this serves: which site folder and how old, live on / off, the Kalshi and money sources
  GET /api/site/launch.json  the Gate's Launch card (tools/launch_card.py): per bot armed? feed fresh? trades, $, drawdown left,
                         flags incl. the real-fill check (tools/fill_check.py), and whether the 15-minute phone report runs

PRIVATE files (team Q2 privacy audit, 2026-11-14, docs/PRIVACY.md): day/ (calendars, the phone inbox), money/household.json +
agency.json (bank exports, agency billing), every money_out/ file (oikos.json is built from the bank exports), and health / cards
(team ME1) are served ONLY to the PC itself (a loopback client, no proxy headers, Host localhost) or through the owner's Tailscale
link (tailscale serve on this PC: X-Forwarded-For a tailnet address, a signed-in Tailscale-User-Login, Host <pc>.<tailnet>.ts.net,
never Funnel, no other tunnel): private_why(). The server listens on 0.0.0.0 (server.py HOST), so without this anyone on the home
WiFi could read them at http://<pc>:8766/site/day/day.json. Over the WiFi the money pages get the build's sample copies instead.
Tests: tests/test_private_link.py.

READ ONLY over the link: a request that came through any proxy (X-Forwarded-For / X-Forwarded-Host / Tailscale-User-Login ...)
may only GET / HEAD / OPTIONS (one exception, only once engine/day_inbox.install ran: POST /inbox/<kind>, which appends a line to
the phone inbox file and nothing else; docs/CONNECT_DAY.md); every other POST, PUT, PATCH, DELETE is refused with 403 before it reaches a route (so nothing can start,
stop, arm or route the bot from the phone link), a Tailscale Funnel request (internet) is refused outright, and the TradingView
webhook key page is hidden. Requests from the PC itself (no proxy headers) are unchanged. Nothing here writes a file, places an
order or reads a secret. Tests: tests/test_live_link.py.
"""
from __future__ import annotations

import ipaddress
import json
import math
import mimetypes
import os
import threading
import time
import urllib.request

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_PUBLIC = os.path.join(ROOT, "tools", "web_public")
SITE_CANDIDATES = (os.path.join(ROOT, "data", "pc_publish", "site"), os.path.join(ROOT, "data", "live_site", "site"))
MONEY_OUT = os.path.join(ROOT, "money_out")
DAY_DIR = os.path.join(ROOT, "data", "day")     # tools/calendar_sync.py OUT_DEFAULT (LE_DAY_DIR overrides, as there)
DAY_FILES = ("day.json", "inbox.json")         # private: served from DAY_DIR only, never looked up in a site folder (inbox.json: engine/day_inbox.py)
ME_DIR = os.path.join(ROOT, "data", "me")       # tools/me_hub.py OUT_DEFAULT (LE_ME_DIR overrides, as there): the Me hub's phone files
ME_FILES = ("me.json", "health.json", "home.json")   # private: served from ME_DIR only, never looked up in a site folder
POST_ALLOW: list = []                           # the only POSTs the phone link may make: engine/day_inbox.allowed (POST /inbox/<kind>), added by its install()
PREFIX = "/site"
GATE = PREFIX + "/gate/"
LIVE_TTL_S = 15
KALSHI_TTL_S = 60
KALSHI_MAX = 300_000
FRESH_S = 20 * 60                       # pc_feed.js FRESH_S: a verdict older than this is not laid over home.json
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "x-real-ip", "forwarded", "tailscale-user-login",
                 "tailscale-funnel-request", "cf-connecting-ip", "true-client-ip")
HIDDEN_OVER_LINK = ("/api/tv/status",)  # shows the TradingView webhook key: the PC only
# PRIVATE routes (private_why): the PC itself or the Tailscale link only, never another device on the WiFi (docs/PRIVACY.md)
PRIVATE_ROUTES = ("day/",)                                    # data/day/: calendars, shifts, the phone inbox (+ health / cards JSON there)
PRIVATE_MONEY = ("household", "agency", "cards", "health")   # money/<name>.json with no public copy at all: 403 for anyone else
LOOPBACK = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
LOCAL_NAMES = ("localhost", "127.0.0.1", "::1")
OTHER_TUNNELS = ("cf-connecting-ip", "true-client-ip", "cf-ray", "fly-client-ip", "x-original-forwarded-for", "x-envoy-external-address",
                 "x-vercel-forwarded-for", "x-nf-client-connection-ip", "x-azure-clientip")
TAILNET = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))   # Tailscale's address ranges
MONEY_KEEP = ("index", "chrysos", "mercury", "sibyl", "oikos", "arbiter", "sibyl_forward")   # tools/money_publish.KEEP
# + the household summary (tools/money_import.py, 2026-11-14): served over this PRIVATE link only, never in money_publish.KEEP
# (the public site never gets it); no account numbers, no merchant names unless the owner turns them on
MONEY_KEEP = MONEY_KEEP + ("household", "agency")   # agency = the billing kit's totals (money_out/agency.json), private link only
TYPES = {".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json",
         ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
         ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8",
         ".md": "text/plain; charset=utf-8", ".csv": "text/csv; charset=utf-8", ".wasm": "application/wasm", ".mp3": "audio/mpeg",
         ".ogg": "audio/ogg", ".wav": "audio/wav", ".mp4": "video/mp4", ".webm": "video/webm", ".woff2": "font/woff2",
         ".woff": "font/woff", ".ttf": "font/ttf", ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".pdf": "application/pdf",
         ".xml": "application/xml", ".gz": "application/gzip"}

_S: dict = {"live": None, "kalshi_cfg": None}


# ------------------------------------------------------------------------------------------------ the read-only guard
def proxied(headers) -> bool:
    """True when the request came through a proxy or tunnel (tailscale serve sets X-Forwarded-For / -Host and, for a person on the
    tailnet, Tailscale-User-Login). The PC's own browser sends none of these."""
    return any(headers.get(h) for h in PROXY_HEADERS)


def guard(method: str, path: str, headers) -> tuple | None:
    """None = let it through; else (status, json body). Pure: tests call it directly."""
    if not proxied(headers):
        return None
    if headers.get("tailscale-funnel-request"):
        return 403, {"ok": False, "error": "this dashboard is private: open it from your own devices on Tailscale, not the internet"}
    if (method or "").upper() not in SAFE_METHODS and not any(_post_ok(f, method, path) for f in POST_ALLOW):
        return 403, {"ok": False, "error": "read only over the phone link: start, stop, arm and settings are done on the PC itself"}
    if path in HIDDEN_OVER_LINK:
        return 403, {"ok": False, "error": "shown on the PC only"}
    return None


def _post_ok(f, method, path) -> bool:
    try:
        return bool(f(method, path))
    except Exception:  # noqa: BLE001
        return False


def allow_post(f) -> None:
    """engine/day_inbox.install: let ONE kind of POST through the link (f(method, path) -> bool; only /inbox/<kind>)"""
    if f not in POST_ALLOW:
        POST_ALLOW.append(f)


def _hostname(v) -> str:
    v = str(v or "").strip().lower()
    if v.startswith("["):
        return v[1:].split("]", 1)[0]
    return v.rsplit(":", 1)[0] if v.count(":") == 1 else v


def tailnet_ip(v) -> bool:
    try:
        ip = ipaddress.ip_address(str(v or "").strip().strip("[]"))
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return any(ip in n for n in TAILNET if n.version == ip.version)


def private_why(client, headers) -> str | None:
    """None = this request may read a PRIVATE file; else why not, in plain words. Allowed: (1) the PC itself: a loopback client, no
    proxy header, Host localhost (a web page that renamed itself to 127.0.0.1 - DNS rebinding - has another Host); (2) the owner's
    Tailscale link: tailscale serve on this PC sets X-Forwarded-For to the phone's tailnet address and Tailscale-User-Login to the
    signed-in user, Host stays <pc>.<tailnet>.ts.net (uvicorn then reports the tailnet address as the client). Refused: any other
    device (the home WiFi), a Funnel (internet) request, another tunnel, a forwarded address outside Tailscale. Pure."""
    h = {str(k).lower(): str(v) for k, v in (headers.items() if hasattr(headers, "items") else [])}
    c = str(client or "").strip()
    host = _hostname(h.get("host", ""))
    if not proxied(h):
        if c in LOOPBACK and host in LOCAL_NAMES:
            return None
        return ("private: open it on the PC itself (http://localhost:8766) or through your Tailscale link, not from another device on "
                "the WiFi" if c not in LOOPBACK else "private: open it on the PC at http://localhost:8766")
    if h.get("tailscale-funnel-request"):
        return "private: never from the internet (Tailscale Funnel is refused)"
    if any(h.get(k) for k in OTHER_TUNNELS):
        return "private: only through your own Tailscale link, not another tunnel"
    xff = [x.strip() for x in h.get("x-forwarded-for", "").split(",") if x.strip()]
    if not xff or not all(tailnet_ip(x) for x in xff) or not (c in LOOPBACK or tailnet_ip(c)):
        return "private: only from your own devices on Tailscale"
    if not h.get("tailscale-user-login", "").strip():
        return "private: only a device signed in to your Tailscale account"
    if not (host.endswith(".ts.net") or host in LOCAL_NAMES):
        return "private: open it at your https://<pc>.<tailnet>.ts.net address"
    return None


def _client(request) -> str:
    return getattr(getattr(request, "client", None), "host", None) or ""


# ------------------------------------------------------------------------------------------------ where the site is
def site_dirs(env=None) -> list:
    """[the newest built site (by its index.html), tools/web_public]: files are looked up in this order."""
    env = os.environ if env is None else env
    cands = [env["LE_SITE_DIR"]] if env.get("LE_SITE_DIR") else list(SITE_CANDIDATES)
    built = []
    for d in cands:
        try:
            built.append((os.path.getmtime(os.path.join(d, "index.html")), d))
        except OSError:
            pass
    out = [max(built)[1]] if built else []
    return out + [WEB_PUBLIC]


def _built_dir(env=None):
    d = site_dirs(env)
    return d[0] if len(d) > 1 else None


def resolve(rel: str, dirs: list) -> tuple:
    """(kind, path): ("file", abs) | ("dir", None) | ("missing", None) | ("bad", None). No "..", no hidden names, never outside
    a site folder (symlinks included)."""
    rel = (rel or "").replace("\\", "/")
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if any(p == ".." or p.startswith(".") or ":" in p or "\x00" in p for p in parts):
        return "bad", None
    want_index = rel == "" or rel.endswith("/")
    for base in dirs:
        broot = os.path.realpath(base)
        p = os.path.realpath(os.path.join(broot, *parts)) if parts else broot
        if p != broot and not p.startswith(broot + os.sep):
            continue
        if os.path.isdir(p):
            idx = os.path.join(p, "index.html")
            if want_index and os.path.isfile(idx):
                return "file", idx
            if not want_index and os.path.isfile(idx):
                return "dir", None
            continue
        if os.path.isfile(p) and not want_index:
            return "file", p
    return "missing", None


def ctype(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return TYPES.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ home.json + the live numbers
def _obj(x) -> bool:
    return isinstance(x, dict)


def _n(v):
    """JS unary plus for the values these files hold: a number, a numeric string, else None (NaN)."""
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, str):
        try:
            x = float(v.strip()) if v.strip() else 0.0
            return x if math.isfinite(x) else None
        except ValueError:
            return None
    if v is None:
        return 0.0
    return None


def _truthy_n(v) -> float:
    x = _n(v)
    return x if x else 0.0


def _bt(b) -> float:
    return (_truthy_n(b.get("data_t")) or _truthy_n(b.get("t"))) if _obj(b) else 0.0


def _js_str(v) -> str:
    if v is None:
        return "undefined"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def merge_trades(a, b) -> list:
    m: dict = {}
    for t in list(a or []) + list(b or []):
        if not _obj(t):
            continue
        k = _js_str(t.get("acct")) + "|" + _js_str(t.get("entry_t") or t.get("day"))
        m[k] = {**m.get(k, {}), **t}
    return sorted(m.values(), key=lambda t: -_truthy_n(t.get("entry_t")))


def merge_board(site, lite):
    s = site if _obj(site) and not site.get("error") else None
    l = lite if _obj(lite) and not lite.get("error") else None
    if not l:
        return s or (site if site else None)
    if not s:
        return l
    if _bt(s) > _bt(l):
        return s
    out = dict(s)
    for k in ("t", "data_t", "where", "today", "host", "running", "level"):
        if l.get(k) is not None:
            out[k] = l[k]
    for k in ("lit", "atlas", "blitz"):
        if _obj(l.get(k)):
            out[k] = {**(s[k] if _obj(s.get(k)) else {}), **l[k]}
    if isinstance(l.get("lines"), list) and l["lines"]:
        out["lines"] = l["lines"]
    out["trades"] = merge_trades(s.get("trades"), l.get("trades"))
    return out


def overlay_home(home, lite, now=None):
    """tools/web_public/pc_feed.js overlayHome in Python (the same result for the same input: tests compare them in node)."""
    lt = _n(lite.get("t")) if _obj(lite) and lite.get("t") is not None else None
    if not _obj(home) or not _obj(lite) or lt is None:
        return home
    now = float(now) if now is not None else time.time()
    live = home["live"] if _obj(home.get("live")) else {}
    pc0 = live["pc"] if _obj(live.get("pc")) else {}
    if lt < _truthy_n(pc0.get("t")):
        return home
    age = max(0.0, now - lt)
    lt_out = int(lt) if float(lt).is_integer() else lt
    pc = {**pc0, **(lite["pc"] if _obj(lite.get("pc")) else {}), "present": True, "t": lt_out, "age_s": int(math.floor(age + 0.5)), "live": True}
    nl = {**live, "pc": pc}
    if age < FRESH_S and _obj(lite.get("pc_verdict")):
        nl["pc_verdict"] = lite["pc_verdict"]
    if _obj(lite.get("reporter")):
        nl["reporter"] = lite["reporter"]
    return {**home, "live": nl, "board": merge_board(home.get("board"), lite.get("board"))}


# ------------------------------------------------------------------------------------------------ the live payload (cached)
class LiveCache:
    """fn() -> the bot's live.json; at most one build every ttl seconds, one at a time. Never raises."""

    def __init__(self, fn, ttl: float = LIVE_TTL_S, clock=time.time):
        self.fn, self.ttl, self.clock = fn, ttl, clock
        self.val, self.at, self.err = None, 0.0, None
        self._lock = threading.Lock()

    def get(self):
        with self._lock:
            if self.val is not None and self.clock() - self.at < self.ttl:
                return self.val
            try:
                v = self.fn() if self.fn else None
                self.val, self.at, self.err = (v if _obj(v) and v.get("kind") == "le-live" else None), self.clock(), None
            except Exception as e:
                self.val, self.at, self.err = None, self.clock(), f"{e.__class__.__name__}: {str(e)[:160]}"
            return self.val


# ------------------------------------------------------------------------------------------------ Kalshi + money
def _kalshi_cfg():
    if _S.get("kalshi_cfg") is not None:
        return _S["kalshi_cfg"]() if callable(_S["kalshi_cfg"]) else _S["kalshi_cfg"]
    try:
        from tools import pc_publish
        return pc_publish.load_config()
    except Exception:
        return {}


_KAL = {"at": 0.0, "raw": None, "src": None, "url": None}


def _small_json_obj(raw) -> bool:
    try:
        return raw is not None and len(raw) <= KALSHI_MAX and isinstance(json.loads(raw.decode("utf-8")), dict)
    except Exception:
        return False


def kalshi(site_dir=None, cfg=None, opener=None, clock=time.time) -> tuple:
    """(bytes, source) of the newest Kalshi feed: the setting's file, its https address (cached 60 s), else the site's copy;
    (None, None) when there is none. Never raises."""
    cfg = _kalshi_cfg() if cfg is None else cfg
    try:
        f = cfg.get("kalshi_file")
        if f:
            with open(os.path.expanduser(str(f)), "rb") as fh:
                raw = fh.read(KALSHI_MAX + 1)
            if _small_json_obj(raw):
                return raw, "file"
        u = str(cfg.get("kalshi_feed_url") or "")
        if u.startswith("https://") or u.startswith("http://127.0.0.1"):
            if _KAL["url"] == u and _KAL["raw"] is not None and clock() - _KAL["at"] < KALSHI_TTL_S:
                return _KAL["raw"], "url"
            try:
                op = opener or (lambda req: urllib.request.urlopen(req, timeout=10))
                with op(urllib.request.Request(u, headers={"User-Agent": "olympus-live-site/1"})) as r:
                    raw = r.read(KALSHI_MAX + 1)
                if _small_json_obj(raw):
                    _KAL.update(at=clock(), raw=raw, src="url", url=u)
                    return raw, "url"
            except Exception:
                if _KAL["url"] == u and _KAL["raw"] is not None:
                    return _KAL["raw"], "url (last good)"
    except Exception:
        pass
    if site_dir:
        p = os.path.join(site_dir, "kalshi.json")
        try:
            with open(p, "rb") as fh:
                raw = fh.read(KALSHI_MAX + 1)
            if _small_json_obj(raw):
                return raw, "site"
        except OSError:
            pass
    return None, None


def money_file(name: str, src: str | None = None):
    """money_out/<name>.json when it is a contract file with valid JSON (what tools/money_publish.py would copy), else None."""
    base, ext = os.path.splitext(name or "")
    if ext != ".json" or base not in MONEY_KEEP or "/" in name or "\\" in name:
        return None
    p = os.path.join(src or MONEY_OUT, name)
    return p if os.path.isfile(p) and read_json(p) is not None else None


def day_file(name: str, env=None):
    """data/day/<name> (your calendars' day, tools/calendar_sync.py) when it is a known file with valid JSON, else None"""
    env = os.environ if env is None else env
    if name not in DAY_FILES:
        return None
    p = os.path.join(env.get("LE_DAY_DIR") or DAY_DIR, name)
    return p if os.path.isfile(p) and read_json(p) is not None else None


def me_file(name: str, env=None):
    """data/me/<name> (the Me hub: tools/me_hub.py, me_health.py, me_home.py) when it is a known file with valid JSON, else None"""
    env = os.environ if env is None else env
    if name not in ME_FILES:
        return None
    p = os.path.join(env.get("LE_ME_DIR") or ME_DIR, name)
    return p if os.path.isfile(p) and read_json(p) is not None else None


# ------------------------------------------------------------------------------------------------ the routes
router = APIRouter()


def _J(obj, status=200, headers=None):
    return Response(json.dumps(obj, separators=(",", ":"), default=str, ensure_ascii=False), media_type="application/json",
                    status_code=status, headers={"Cache-Control": "no-store", **(headers or {})})


def _live():
    c = _S.get("live")
    return c.get() if c is not None else None


@router.get("/api/site/live.json")
def r_live():
    v = _live()
    if v is None:
        c = _S.get("live")
        return _J({"ok": False, "error": "the bot's live numbers are not available on this server" + (f" ({c.err})" if c and c.err else "")}, 503)
    return _J(v)


@router.get("/api/site/status")
def r_status():
    d = _built_dir()
    built_t = None
    if d:
        try:
            built_t = int(os.path.getmtime(os.path.join(d, "index.html")))
        except OSError:
            pass
    _raw, ksrc = kalshi(d)
    m = money_file("index.json")
    return _J({"ok": True, "t": int(time.time()), "site": {"built": bool(d), "dir": os.path.relpath(d, ROOT).replace("\\", "/") if d else None,
                                                         "built_t": built_t, "fallback": "tools/web_public"},
               "live": _live() is not None, "kalshi": ksrc, "money": "money_out" if m else ("site" if d else None), "home": GATE,
               "me": bool(me_file("me.json"))})


@router.get("/api/site/launch.json")
def r_launch():
    """The Launch card (tools/launch_card.py, Monday launch kit 2026-11-14): per bot armed? feed fresh? trades, $, drawdown left,
    flags (the fill check, tools/fill_check.py); is the phone report running. Read-only, like everything here."""
    try:
        from tools import launch_card
        return _J(launch_card.payload(_live()))
    except Exception as e:
        return _J({"ok": False, "error": f"the launch card could not be built ({e.__class__.__name__})"}, 503)


@router.api_route(PREFIX, methods=["GET", "HEAD"])
def r_site_root():
    return RedirectResponse(GATE, status_code=307)


@router.api_route(PREFIX + "/{rel:path}", methods=["GET", "HEAD"])
def r_site(rel: str, request: Request):
    dirs = site_dirs()
    built = dirs[0] if len(dirs) > 1 else None
    low = "/".join(x for x in (rel or "").replace("\\", "/").lower().split("/") if x not in ("", "."))
    why = private_why(_client(request), request.headers)
    if why and low.startswith(PRIVATE_ROUTES):
        return _J({"ok": False, "error": why}, 403)
    if rel == "home.json":
        home = read_json(os.path.join(built, "home.json")) if built else None
        lv = _live()
        if home is None and lv is None:
            return _J({"ok": False, "error": "no home.json yet: the site is built every 15 minutes (LIVE_LINK.bat sets it up)"}, 404)
        out = overlay_home(home if _obj(home) else {}, lv) if lv is not None else home
        return _J(out, headers={"X-Olympus-Source": "built+live" if (home is not None and lv is not None) else ("live" if lv is not None else "built")})
    if rel == "kalshi.json":
        raw, src = kalshi(built)
        if raw is None:
            return _J({"ok": False, "error": "no Kalshi feed on this PC yet"}, 404)
        return Response(raw, media_type="application/json", headers={"Cache-Control": "no-store", "X-Olympus-Source": src})
    if rel.startswith("money/"):
        p = money_file(rel[len("money/"):]) if why is None else None      # money_out = the PC's real money: private
        if p:
            return FileResponse(p, media_type="application/json", headers={"Cache-Control": "no-store", "X-Olympus-Source": "money_out"})
        if why and os.path.splitext(low[len("money/"):])[0] in PRIVATE_MONEY:
            return _J({"ok": False, "error": why}, 403)
        # anyone else gets the build's public (sample) copy below, like the Netlify site
    if rel.startswith("day/"):
        name = rel[len("day/"):]
        p = day_file(name)
        if p:
            return FileResponse(p, media_type="application/json", headers={"Cache-Control": "no-store", "X-Olympus-Source": "calendar_sync"})
        if name in DAY_FILES:
            return _J({"ok": False, "error": "no calendar connected on this PC yet (CONNECT_DAY.bat, docs/CONNECT_DAY.md)"}, 404)
        return _J({"ok": False, "error": "not found"}, 404)
    if rel.startswith("me/"):
        name = rel[len("me/"):]
        p = me_file(name)
        if p:
            return FileResponse(p, media_type="application/json", headers={"Cache-Control": "no-store", "X-Olympus-Source": "me_hub"})
        if name in ME_FILES:
            return _J({"ok": False, "error": "the Me hub has not been made on this PC yet (it runs with the PC report; docs/ME_HUB.md)"}, 404)
        return _J({"ok": False, "error": "not found"}, 404)
    kind, path = resolve(rel, dirs)
    if kind == "file":
        return FileResponse(path, media_type=ctype(path), headers={"Cache-Control": "no-cache"})
    if kind == "dir":
        q = request.url.query
        return RedirectResponse(PREFIX + "/" + rel.rstrip("/") + "/" + ("?" + q if q else ""), status_code=307)
    return _J({"ok": False, "error": "not found" if kind == "missing" else "bad path"}, 404 if kind == "missing" else 400)


def install(app, live=None, kalshi_cfg=None) -> dict:
    """Add the read-only guard, the Gate redirect for the phone link and the /site + /api/site routes. Call it before the app's
    catch-all static mount. live: a function returning the bot's live.json (server.py: LIVEPUB.payload)."""
    _S["live"] = LiveCache(live) if live is not None else None
    _S["kalshi_cfg"] = kalshi_cfg

    @app.middleware("http")
    async def live_link_guard(request, call_next):
        bad = guard(request.method, request.url.path, request.headers)
        if bad is not None:
            return JSONResponse(bad[1], status_code=bad[0])
        if request.url.path == "/" and request.method in ("GET", "HEAD") and proxied(request.headers):
            return RedirectResponse(GATE, status_code=307)
        return await call_next(request)

    app.include_router(router)
    return {"site": site_dirs(), "live": live is not None}
