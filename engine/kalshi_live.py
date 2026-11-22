"""KALSHI LIVE executor (night-klive 2026-11-19; owner: "Kalshi, take our best shot and send it live").

OFF by default. It trades real money ONLY after the owner types the phrase  I ACCEPT KALSHI LIVE RISK  at the PC
(KALSHI_LIVE.bat), and it switches itself OFF again after ANY stop (daily loss stop, kill switch, phone FLATTEN / KILL, plan
change, a new executor version, Kalshi refusing the key or our orders, Kalshi not answering for 15 minutes). Claude never
arms it, never types the phrase, never places an order: every test runs on a fake Kalshi.

What it runs: the strategy plan file research/lab/kalshi_live_plan.json (written by the research helpers; shape below) and
the taker candidates research/lab/kalshi_candidates/*.json whose status is proposal / approved / ready / live. The plan
and the candidates are hashed when the owner arms: any change to them later = stop + OFF until he types the phrase again.

  rewards_maker  on the markets of each plan series that have an active Kalshi liquidity-rewards program: ONE resting,
                 post-only bid per side (YES bid + NO bid = a YES ask) at the reward reference price minus offset_cents,
                 `size` contracts, renewed before it expires (every order carries expiration_time = now + 20 min, so a dead
                 PC leaves nothing resting for long). Pauses: 1 h before the close (or the plan's), the plan's "pause" rules
                 (after_move / before_close / wide_spread / program_end), one-sided or 20c+ wide books.
  taker          (candidates) buy the side whose taker price is in price_band inside decide_hours_before_close, one bet per
                 market, size_usd_per_bet, limit immediate-or-cancel (never a market order).

Safety, all in code (check_order runs before EVERY order; each cap has a test):
  armed (typed phrase, plan + executor version unchanged), kill switch off, not paused, not stopped; maker quotes must be
  post-only + good-till-canceled + expiring within 20 min; price 2c-98c, never crossing the book, prices under 90 s old;
  market open; contracts per order; per-market cap (resting + held, account-wide); capital cap (all resting + all held);
  cash on Kalshi; max open orders (account-wide); daily loss stop (and no order that could lose more than the room left);
  at most 30 orders a minute and 1,500 a day. Hard ceilings in code whatever the plan says: $250 total, $50 a market,
  -$25 a day, 40 orders, 100 contracts, 12 markets. Only these Kalshi calls exist: GET reads, POST /portfolio/events/orders,
  DELETE /portfolio/events/orders/<id> | /batched (no transfer, withdrawal or key endpoint can be reached).
Every loop (60 s) reconciles with Kalshi first: cash, positions, resting orders (ours = client_order_id 'olyk-...', adopted
after a restart), fills and settlements; positions that do not match the fills for 3 loops = stop. Day P&L (ET day) =
cash from today's fills and settlements + positions at the mid now - positions at the mid at the day's start (Kalshi's
liquidity rewards are paid separately and are NOT counted: the stop is conservative). Cash falling more than capital cap +
daily stop in a day = stop.

Phone: the ZEUS Safety page (engine/phone_safety.py) presses reach Kalshi too: PAUSE (our quotes cancelled, no new orders
until the next 4 PM ET), RESUME (lifts it, never arms), FLATTEN (cancel ALL resting orders + sell what Kalshi holds at the best
price, reduce-only immediate-or-cancel, then OFF), KILL (the same + the kill switch file). KALSHI_STOP.bat = cancel all + OFF
(positions are kept: they settle by themselves).

Alerts: few (ntfy allows ~250 a day per IP and the PC's status posts use ~210): fills batched (at most one push an hour,
6 a day), one day summary, armed once, stops at once (always). At most 10 non-stop pushes per ET day. Private topic only
(engine/notify.alert_cfg), no ids, no key.

Key (never in the repo, never printed): %USERPROFILE%\\.olympus\\kalshi\\kalshi_key.pem + key_id.txt (KALSHI_KEY_SETUP.bat
moves the downloaded key there and locks it to the Windows user), or the user variables KALSHI_KEY_FILE / KALSHI_KEY_ID.
RSA-PSS or Ed25519 signing as docs.kalshi.com says (timestamp ms + METHOD + /trade-api/v2/path, no query).

Files (gitignored): data/kalshi_live/ arm.json (armed + proof hash; the phrase itself is never stored), state.json, control.json
(phone / PC commands), KILL, log.jsonl, card.json (the <=200-byte public card), run.json, loop.lock.
LE_KALSHI_LIVE=0 forces it OFF everywhere.

  python -X utf8 -m engine.kalshi_live                 status in plain words
  python -X utf8 -m engine.kalshi_live --dry-run       what it would place now, from public prices (no key, nothing sent)
  python -X utf8 -m engine.kalshi_live --check-key     one signed read (balance): is the key right?
  python -X utf8 -m engine.kalshi_live --go            KALSHI_LIVE.bat: plan + key + dry run, YOU type the phrase, then it runs
  python -X utf8 -m engine.kalshi_live --stop          KALSHI_STOP.bat: cancel every resting order, OFF
  python -X utf8 -m engine.kalshi_live --pause | --resume | --flatten
PC 15-minute report hook (lead): maybe_run() restarts the loop after a PC restart only while armed; read_card() = the card.
Tests: python -X utf8 -m tests.test_kalshi_live

Plan file shape (version 1): {"version": 1, "strategy": "rewards_maker", "status": "proposal", "capital_cap_usd", "per_market_cap_usd",
"daily_loss_stop_usd", "max_open_orders", "markets": [{"series", "why", "quote": {"offset_cents", "size"}, "pause": [...],
optional "max_markets" (2), "tickers"}], "evidence": {...}, "unproven": [...]}. Pause rules: {"type": "before_close", "hours": 2},
{"type": "after_move", "cents": 5, "minutes": 60}, {"type": "wide_spread", "cents": 10}, {"type": "program_end", "minutes": 30} or
the strings "close_2h", "move_5c_60m", "spread_10c", "program_end_30m"; a rule it does not understand = that market is skipped.
"""
from __future__ import annotations

import base64
import datetime as dt
import glob
import hashlib
import json
import math
import os
import re
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXEC_VERSION = "2026-11-21.1"          # bump when the trading logic changes: an armed PC then needs the phrase again
PHRASE = "I ACCEPT KALSHI LIVE RISK"
PLAN_PATH = os.path.join(ROOT, "research", "lab", "kalshi_live_plan.json")
CAND_DIR = os.path.join(ROOT, "research", "lab", "kalshi_candidates")
STATE_DIR = os.path.join(ROOT, "data", "kalshi_live")
API_PATH = "/trade-api/v2"
API_BASE = "https://api.elections.kalshi.com" + API_PATH        # the host this project already reads (docs: still supported)
API_HOSTS = ("api.elections.kalshi.com", "external-api.kalshi.com", "demo-api.kalshi.co", "external-api.demo.kalshi.co")
LOOPBACK = ("127.0.0.1", "localhost", "::1")
UA = "olympus-kalshi-live/" + EXEC_VERSION
COID = "olyk-"                          # our client_order_id prefix (orders without it are never ours)
ALLOWED_STATUS = ("proposal", "approved", "ready", "live")
HARD = {"capital_cap_usd": 250.0, "per_market_cap_usd": 50.0, "daily_loss_stop_usd": 25.0, "max_open_orders": 40, "size": 100,
        "markets": 12, "offset_cents": 10, "size_usd_per_bet": 25.0}
DEFAULT_CAPS = {"capital_cap_usd": 50.0, "per_market_cap_usd": 10.0, "daily_loss_stop_usd": 10.0, "max_open_orders": 10}
MIN_PX, MAX_PX = 0.02, 0.98
BOOK_MAX_AGE_S = 90
ORDER_TTL_S = 20 * 60                   # dead-man switch: Kalshi cancels every resting order of ours after 20 min by itself
RENEW_BEFORE_S = 5 * 60
MAX_ORDERS_MIN, MAX_ORDERS_DAY = 30, 1500
LOOP_S = 60
FAIL_STOP_S = 15 * 60
REJECT_STOP = 3
MISMATCH_STOP = 3
PROG_REFRESH_S = 600
DEFAULT_CLOSE_H = 1.0
WIDE_SPREAD = 0.20
PROGRAM_END_S = 15 * 60
PUSH_DAY_MAX = 10                       # non-stop pushes per ET day (stops always go)
FILL_PUSH_GAP_S, FILL_PUSH_DAY_MAX = 3600, 6
HEARTBEAT_STALE_S = 300
CARD_MAX = 600                          # 200 + the K8 status block (about 130 bytes, night-kalshi8) + day stop, edge health, last 5 bets, per-leg last 20, checklist flags, $ today/week/all (day-kalshi)
TICKER_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
PLAIN = {
    "KILL": "the kill switch is on", "NOT_ARMED": "not armed: type the phrase on the PC", "STOPPED": "stopped: type the phrase again",
    "PAUSED": "paused from the phone or the PC", "BAD_ORDER": "the order is not valid", "NOT_MAKER": "only resting post-only orders",
    "EXPIRY": "every resting order must expire within 20 minutes", "PRICE": "price outside 2c-98c", "SIZE": "too many contracts",
    "MARKET_CLOSED": "the market is not open", "STALE_BOOK": "the prices are too old", "CROSS": "it would cross the book",
    "MARKET_CAP": "per-market cap", "CAPITAL_CAP": "capital cap", "BALANCE": "not enough cash on Kalshi",
    "OPEN_ORDERS": "too many orders resting", "DAY_STOP": "the daily loss stop is reached", "STOP_ROOM": "more than the room left today",
    "RATE": "too many orders in a minute", "DAY_ORDERS": "too many orders today", "BAND": "price outside the rule's band",
    "NOT_HELD": "it would not reduce what Kalshi holds", "ERROR": "the check hit an error (blocked to be safe)",
}


# ================================================================================================ small helpers
def _f(x, d=None):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return d
    return v if math.isfinite(v) else d


def _ts(s):
    if s in (None, ""):
        return None
    if isinstance(s, (int, float)):
        return float(s)
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _cnt(o, name):
    """Kalshi count: name_fp (fixed point string) or the legacy integer."""
    v = _f(o.get(name + "_fp"))
    return v if v is not None else _f(o.get(name), 0.0)


def _px(o, name):
    """Kalshi price in dollars: name_dollars or the legacy cents integer. None when absent."""
    v = _f(o.get(name + "_dollars"))
    if v is not None:
        return v
    c = _f(o.get(name))
    return None if c is None else c / 100.0


def _usd(o, name):
    v = _f(o.get(name + "_dollars"))
    if v is not None:
        return v
    c = _f(o.get(name))
    return 0.0 if c is None else c / 100.0


def money(x, sign=False) -> str:
    v = _f(x, 0.0)
    s = "-" if v < -0.004 else ("+" if sign and v > 0.004 else "")
    return f"{s}${abs(v):,.2f}"


try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001  (no tzdata: the US rule by hand)
    _ET = None


def _et_offset(t):
    y = dt.datetime.fromtimestamp(t, dt.timezone.utc).year

    def nth_sunday(month, n):
        d = dt.date(y, month, 1)
        return d + dt.timedelta(days=(6 - d.weekday()) % 7 + 7 * (n - 1))

    a = dt.datetime.combine(nth_sunday(3, 2), dt.time(7), dt.timezone.utc).timestamp()
    b = dt.datetime.combine(nth_sunday(11, 1), dt.time(6), dt.timezone.utc).timestamp()
    return -4 * 3600 if a <= t < b else -5 * 3600


def et_dt(t) -> dt.datetime:
    if _ET is not None:
        return dt.datetime.fromtimestamp(t, _ET)
    return dt.datetime.fromtimestamp(t + _et_offset(t), dt.timezone.utc).replace(tzinfo=None)


def et_day(t) -> str:
    return et_dt(t).date().isoformat()


def et_text(t) -> str:
    d = et_dt(t)
    return f"{d:%a} {d:%b} {d.day}, {d.hour % 12 or 12}:{d:%M} {'AM' if d.hour < 12 else 'PM'} ET"


def next_4pm(t) -> float:
    """The next 4 PM ET (the phone PAUSE's end, as engine/phone_safety: pressed in the day = today, at night = tomorrow)."""
    d = et_dt(t)
    for add in range(0, 3):
        day = (d + dt.timedelta(days=add)).date()
        if _ET is not None:
            cand = dt.datetime(day.year, day.month, day.day, 16, 0, tzinfo=_ET).timestamp()
        else:
            noon = dt.datetime(day.year, day.month, day.day, 12, tzinfo=dt.timezone.utc).timestamp()
            cand = dt.datetime(day.year, day.month, day.day, 16, tzinfo=dt.timezone.utc).timestamp() - _et_offset(noon)
        if cand > t:
            return cand
    return t + 86400


def iso(t) -> str:
    return dt.datetime.fromtimestamp(float(t), dt.timezone.utc).isoformat(timespec="seconds")


def _jread(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _jwrite(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"))
    _replace(tmp, path)


def _replace(src, dst):
    """A file replace with engine/fsutil's retries (Windows: a reader, antivirus or OneDrive holding the file for a moment)."""
    from engine import fsutil
    fsutil.replace(src, dst)


def paths(state_dir=None) -> dict:
    d = state_dir or STATE_DIR
    j = os.path.join
    return {"dir": d, "arm": j(d, "arm.json"), "state": j(d, "state.json"), "control": j(d, "control.json"), "kill": j(d, "KILL"),
            "log": j(d, "log.jsonl"), "card": j(d, "card.json"), "run": j(d, "run.json"), "lock": j(d, "loop.lock"),
            "out": j(d, "loop.log")}


def log(P, row: dict):
    try:
        os.makedirs(P["dir"], exist_ok=True)
        if os.path.exists(P["log"]) and os.path.getsize(P["log"]) > 2_000_000:
            _replace(P["log"], P["log"] + ".1")
        with open(P["log"], "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, separators=(",", ":"), default=str) + "\n")
    except Exception:  # noqa: BLE001
        pass


def off_by_env(env=None) -> bool:
    e = os.environ if env is None else env
    return str(e.get("LE_KALSHI_LIVE", "")).strip() == "0"


def olympus_dir(env=None) -> str:
    try:
        from engine import nogithub
        return nogithub.olympus_dir(env)
    except Exception:  # noqa: BLE001
        e = os.environ if env is None else env
        return e.get("OLYMPUS_HOME") or os.path.join(e.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


# ================================================================================================ the key (outside the repo)
_PEM = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|$)", re.S)
_PATHLIKE = re.compile(r"(?:[A-Za-z]:\\|\\\\|/home/|/Users/|/root/|~[/\\])[^\s'\"<>|]*")


def key_files(env=None) -> dict:
    e = os.environ if env is None else env
    d = os.path.join(olympus_dir(env), "kalshi")
    kf = str(e.get("KALSHI_KEY_FILE") or "").strip().strip('"') or os.path.join(d, "kalshi_key.pem")
    kid = str(e.get("KALSHI_KEY_ID") or "").strip()
    if not kid:
        try:
            with open(os.path.join(d, "key_id.txt"), encoding="utf-8-sig") as fh:
                kid = fh.read().strip()
        except OSError:
            kid = ""
    return {"dir": d, "key_file": os.path.expanduser(os.path.expandvars(kf)), "key_id": kid}


def inside_repo(path) -> bool:
    try:
        a, r = os.path.realpath(path), os.path.realpath(ROOT)
        return os.path.commonpath([a, r]) == r
    except ValueError:
        return False


def load_key(path):
    """The private key (RSA PKCS#1 / PKCS#8 or Ed25519 PEM). Raises KalshiError in plain words; never shows the key."""
    if inside_repo(path):
        raise KalshiError("the Kalshi key file is inside the bot folder: double-click KALSHI_KEY_SETUP.bat to move it out", code="key_in_repo")
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        raise KalshiError("no Kalshi key on this PC: double-click KALSHI_KEY_SETUP.bat", code="no_key") from None
    try:
        from cryptography.hazmat.primitives import serialization
    except Exception:  # noqa: BLE001
        raise KalshiError("the 'cryptography' package is missing: python -m pip install cryptography", code="no_crypto") from None
    try:
        data = data.replace(b"\r\n", b"\n").lstrip(b"\xef\xbb\xbf").strip() + b"\n"
        return serialization.load_pem_private_key(data, password=None)
    except Exception:  # noqa: BLE001
        raise KalshiError("the Kalshi key file is not a private key (it starts with -----BEGIN ... PRIVATE KEY-----)", code="bad_key") from None


def sign(key, ts_ms, method, path) -> str:
    """docs.kalshi.com: base64 signature over timestamp(ms) + METHOD + path from the API root (/trade-api/v2/...), no query.
    RSA: PSS, MGF1(SHA-256), salt = digest length, SHA-256. Ed25519: the message directly."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ed25519, padding
    msg = f"{ts_ms}{method.upper()}{str(path).split('?')[0]}".encode("utf-8")
    if isinstance(key, ed25519.Ed25519PrivateKey):
        sig = key.sign(msg)
    else:
        sig = key.sign(msg, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
    return base64.b64encode(sig).decode("ascii")


def redact(text, secrets_=()) -> str:
    s = _PEM.sub("<key>", str(text or ""))
    for x in sorted({str(x) for x in secrets_ if x and len(str(x)) >= 4}, key=len, reverse=True):
        s = s.replace(x, "<redacted>")
    s = re.sub(r"(?i)(kalshi-access-(?:key|signature|timestamp)\W+)[^\s,;'\"}]+", r"\1<redacted>", s)
    s = re.sub(r"[A-Za-z0-9+/]{60,}={0,2}", "<redacted>", s)
    return _PATHLIKE.sub("<path>", s)[:400]


# ================================================================================================ the Kalshi client
class KalshiError(Exception):
    def __init__(self, msg, status=None, code=None):
        super().__init__(msg)
        self.status, self.code = status, code


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise KalshiError(f"refused a redirect (HTTP {code}): signed requests stay on Kalshi's API", status=code, code="redirect")


def check_base(base) -> str:
    try:
        u = urllib.parse.urlsplit(str(base or ""))
        host, port = (u.hostname or "").lower(), u.port
    except ValueError:
        raise KalshiError("refused: the API address is not a URL", code="base") from None
    ok = (u.scheme == "https" and host in API_HOSTS and port in (None, 443)) or (u.scheme in ("http", "https") and host in LOOPBACK)
    if not ok or u.username or u.password or u.query or u.fragment or u.path.rstrip("/") != API_PATH:
        raise KalshiError("refused: the API address must be Kalshi's trade API (https://<kalshi host>/trade-api/v2)", code="base")
    netloc = f"[{host}]" if ":" in host else host
    return f"{u.scheme}://{netloc}{'' if port is None else ':' + str(port)}{API_PATH}"


_READS = ("/exchange/status", "/portfolio/balance", "/portfolio/positions", "/portfolio/orders", "/portfolio/fills",
          "/portfolio/settlements", "/incentive_programs", "/markets")
_MARKET_RX = re.compile(r"/markets/[A-Za-z0-9._-]{1,128}(/orderbook)?")
_CANCEL_RX = re.compile(r"/portfolio/events/orders/[A-Za-z0-9_-]{1,80}")


def allowed(method, path) -> bool:
    """The whole list of Kalshi calls this executor can make (anything else is refused before a request is built)."""
    m, p = str(method or "").upper(), str(path or "")
    if not p.startswith("/") or any(x in p for x in ("?", "#", "..", "//", "\\", " ")):
        return False
    if m == "GET":
        return p in _READS or bool(_MARKET_RX.fullmatch(p))
    if m == "POST":
        return p == "/portfolio/events/orders"
    if m == "DELETE":
        return bool(_CANCEL_RX.fullmatch(p))
    return False


class Api:
    """Kalshi trade API v2. Public GETs need no key (the dry run); portfolio calls are signed. `http(method, url, headers, data,
    timeout) -> (status, body bytes)` is injectable (tests: a fake Kalshi that checks every signature)."""

    def __init__(self, base=None, key_id=None, key=None, http=None, sleep=time.sleep, clock=time.time, gap=0.12, timeout=15.0,
                 secrets_=()):
        self.root = check_base(base or API_BASE)[: -len(API_PATH)]
        self.key_id, self.key = (str(key_id) if key_id else None), key
        self.secrets = tuple(x for x in secrets_ if x) + ((self.key_id,) if self.key_id else ())
        self.sleep, self.clock, self.gap, self.timeout = sleep, clock, gap, timeout
        self.calls, self.writes, self._last = 0, 0, 0.0
        if http is None:
            host = urllib.parse.urlsplit(self.root).hostname or ""
            handlers = [_NoRedirect()] + ([urllib.request.ProxyHandler({})] if host in LOOPBACK else [])
            opener = urllib.request.build_opener(*handlers)

            def http(method, url, headers, data, timeout):
                req = urllib.request.Request(url, data=data, method=method, headers=headers)
                try:
                    with opener.open(req, timeout=timeout) as r:
                        return r.status, r.read()
                except urllib.error.HTTPError as e:
                    try:
                        return e.code, e.read()
                    except Exception:  # noqa: BLE001
                        return e.code, b""
        self.http = http

    @property
    def has_key(self) -> bool:
        return bool(self.key_id and self.key is not None)

    def _pace(self):
        w = self._last + self.gap - time.monotonic()
        if w > 0:
            self.sleep(w)
        self._last = time.monotonic()

    def call(self, method, path, params=None, body=None, auth=True):
        method = str(method).upper()
        if not allowed(method, path):
            raise KalshiError(f"refused: {method} {path} is not a call this executor may make", code="refused")
        if auth and not self.has_key:
            raise KalshiError("no Kalshi key on this PC: double-click KALSHI_KEY_SETUP.bat", code="no_key")
        full = API_PATH + path
        q = {k: v for k, v in (params or {}).items() if v is not None}
        qs = ("?" + urllib.parse.urlencode(q)) if q else ""
        data = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
        for attempt in range(3):
            self._pace()
            h = {"Accept": "application/json", "User-Agent": UA}
            if data is not None:
                h["Content-Type"] = "application/json"
            if auth:
                ts = str(int(self.clock() * 1000))
                h.update({"KALSHI-ACCESS-KEY": self.key_id, "KALSHI-ACCESS-TIMESTAMP": ts,
                          "KALSHI-ACCESS-SIGNATURE": sign(self.key, ts, method, full)})
            try:
                status, raw = self.http(method, self.root + full + qs, h, data, self.timeout)
            except KalshiError:
                raise
            except Exception as e:  # noqa: BLE001
                if method == "GET" and attempt < 1:
                    self.sleep(1.0)
                    continue
                raise KalshiError(redact(f"no answer from Kalshi on {method} {path} ({e.__class__.__name__}: {e})", self.secrets),
                                  code="network") from None
            self.calls += 1
            self.writes += method != "GET"
            try:
                j = json.loads((raw or b"{}").decode("utf-8", "replace") or "{}")
            except ValueError:
                j = {}
            if 200 <= int(status) < 300:
                return j if isinstance(j, dict) else {}
            err = j.get("error") if isinstance(j, dict) and isinstance(j.get("error"), dict) else (j if isinstance(j, dict) else {})
            code = str(err.get("code") or "")
            if status == 429 and attempt < 2:
                self.sleep(1.0 + attempt)
                continue
            if int(status) >= 500 and method == "GET" and attempt < 1:
                self.sleep(1.0)
                continue
            msg = f"HTTP {status} {code} on {method} {path}: {err.get('message') or ''} {err.get('details') or ''}".strip()
            raise KalshiError(redact(msg, self.secrets), status=int(status), code=code)
        raise KalshiError(f"Kalshi kept saying too many requests on {method} {path}", status=429, code="too_many_requests")

    def get(self, path, params=None, auth=True):
        return self.call("GET", path, params, auth=auth)

    def pages(self, path, key, params=None, max_pages=10, auth=True):
        out, cursor = [], None
        for _ in range(max_pages):
            q = dict(params or {})
            if cursor:
                q["cursor"] = cursor
            j = self.get(path, q, auth=auth)
            rows = j.get(key) if isinstance(j, dict) else None
            out.extend(r for r in (rows or []) if isinstance(r, dict))
            cursor = (j.get("cursor") or j.get("next_cursor")) if isinstance(j, dict) else None
            if not cursor or not rows:
                break
        return out


def api_from_key(env=None, http=None, base=None, **kw) -> Api:
    """The owner's key from outside the repo. Raises KalshiError (plain words) when it is missing / inside the repo / not a key."""
    e = os.environ if env is None else env
    kf = key_files(env)
    if not kf["key_id"]:
        raise KalshiError("no Kalshi key id on this PC: double-click KALSHI_KEY_SETUP.bat", code="no_key")
    key = load_key(kf["key_file"])
    return Api(base=base or e.get("KALSHI_API_BASE") or API_BASE, key_id=kf["key_id"], key=key, http=http,
               secrets_=(kf["key_file"], os.path.basename(kf["key_file"]), kf["dir"]), **kw)


# ================================================================================================ Kalshi rows -> plain dicts
def norm_book(j):
    """(yes bids, no bids), best (highest) first, prices in dollars. orderbook_fp (dollar strings) or the legacy cents."""
    o = (j or {}).get("orderbook_fp")
    if isinstance(o, dict):
        yes = [(_f(a), _f(b)) for a, b in (o.get("yes_dollars") or [])]
        no = [(_f(a), _f(b)) for a, b in (o.get("no_dollars") or [])]
    else:
        o = (j or {}).get("orderbook") or {}
        yes = [((_f(a) or 0) / 100.0, _f(b)) for a, b in (o.get("yes") or [])]
        no = [((_f(a) or 0) / 100.0, _f(b)) for a, b in (o.get("no") or [])]

    def clean(lv):
        return sorted([(round(p, 4), q) for p, q in lv if p is not None and q and q > 0 and 0 < p < 1], reverse=True)
    return clean(yes), clean(no)


def norm_market(j) -> dict:
    m = (j or {}).get("market") if isinstance((j or {}).get("market"), dict) else (j or {})
    steps = []
    for r in m.get("price_ranges") or []:
        if isinstance(r, dict) and _f(r.get("step")):
            steps.append((_f(r.get("start"), 0.0), _f(r.get("end"), 1.0), _f(r.get("step"))))
    return {"ticker": m.get("ticker"), "status": str(m.get("status") or ""), "close_ts": _ts(m.get("close_time")),
            "result": str(m.get("result") or ""), "title": str(m.get("yes_sub_title") or m.get("title") or m.get("ticker") or "")[:80],
            "event": m.get("event_ticker"), "steps": steps}


_BOOK_OF = {("yes", "buy"): "bid", ("yes", "sell"): "ask", ("no", "buy"): "ask", ("no", "sell"): "bid"}


def _book_side(o):
    b = o.get("book_side")
    if b in ("bid", "ask"):
        return b
    return _BOOK_OF.get((o.get("side"), o.get("action")))


def norm_order(o) -> dict:
    y = _px(o, "yes_price")
    if y is None:
        n = _px(o, "no_price")
        y = None if n is None else round(1 - n, 4)
    return {"id": str(o.get("order_id") or ""), "coid": str(o.get("client_order_id") or ""), "ticker": o.get("ticker"),
            "book": _book_side(o), "price": y, "remaining": _cnt(o, "remaining_count"), "status": o.get("status"),
            "exp": _ts(o.get("expiration_time"))}


def norm_fill(f) -> dict:
    y = _px(f, "yes_price")
    if y is None:
        n = _px(f, "no_price")
        y = None if n is None else round(1 - n, 4)
    return {"id": str(f.get("fill_id") or f.get("trade_id") or ""), "order_id": str(f.get("order_id") or ""),
            "ticker": f.get("ticker") or f.get("market_ticker"), "book": _book_side(f), "n": _cnt(f, "count"), "y": y,
            "fee": _f(f.get("fee_cost")), "taker": bool(f.get("is_taker")), "ts": _ts(f.get("created_time")) or _f(f.get("ts"))}


def norm_settlement(s) -> dict:
    v = _f(s.get("value"))
    return {"ticker": s.get("ticker"), "result": str(s.get("market_result") or ""), "yes": _cnt(s, "yes_count"),
            "no": _cnt(s, "no_count"), "value": None if v is None else v / 100.0, "ts": _ts(s.get("settled_time"))}


def norm_positions(rows) -> dict:
    out = {}
    for r in rows or []:
        t = r.get("ticker") or r.get("market_ticker")
        if not t:
            continue
        out[t] = {"pos": _cnt(r, "position"), "exposure": abs(_usd(r, "market_exposure")), "fees": _usd(r, "fees_paid")}
    return out


def fee_est(y, n, taker) -> float:
    """Kalshi's fee when a fill row has none: 0.07 (taker) / 0.0175 (maker) x n x p x (1-p), rounded up to the cent."""
    r = 0.07 if taker else 0.0175
    return math.ceil(r * n * y * (1 - y) * 100 - 1e-9) / 100.0


# ================================================================================================ the plan (pure)
def parse_pause(rules) -> tuple:
    """-> (rules as dicts, problems). Unknown rule = a problem (that market is then skipped: fail closed)."""
    out, probs = [], []
    for r in rules or []:
        d = None
        if isinstance(r, dict):
            typ = str(r.get("type") or r.get("rule") or r.get("kind") or "").lower().replace("-", "_").replace(" ", "_")
            if not typ:                                    # {"hours_before_close": 2} / {"move_cents": 5, "minutes": 60} / {"spread_cents": 10}
                if r.get("hours_before_close") is not None:
                    typ, r = "before_close", {"hours": r.get("hours_before_close")}
                elif r.get("move_cents") is not None:
                    typ, r = "after_move", {"cents": r.get("move_cents"), "minutes": r.get("minutes"), "hours": r.get("hours")}
                elif r.get("spread_cents") is not None:
                    typ, r = "wide_spread", {"cents": r.get("spread_cents")}
            if typ in ("before_close", "close", "pull_before_close"):
                h = _f(r.get("hours"), _f(r.get("minutes"), 0) / 60.0 if r.get("minutes") is not None else None)
                d = {"type": "before_close", "hours": h} if h is not None and 0 <= h <= 72 else None
            elif typ in ("after_move", "move", "price_move", "jump"):
                c, m = _f(r.get("cents")), _f(r.get("minutes"), (_f(r.get("hours"), 0) or 0) * 60 or None)
                d = {"type": "after_move", "cents": c, "minutes": m} if c and m and 0 < c <= 50 and 0 < m <= 1440 else None
            elif typ in ("wide_spread", "spread"):
                c = _f(r.get("cents"))
                d = {"type": "wide_spread", "cents": c} if c and 0 < c <= 50 else None
            elif typ in ("program_end", "reward_end"):
                m = _f(r.get("minutes"))
                d = {"type": "program_end", "minutes": m} if m is not None and 0 <= m <= 1440 else None
        elif isinstance(r, str):
            s = r.strip().lower()
            num_ = r"(\d+(?:\.\d+)?)"
            unit = r"(m|min|minutes?|h|hours?)"
            m_close = (re.fullmatch(r"(?:before_)?close[_:\s-]*" + num_ + r"\s*h(?:ours?)?", s)
                       or re.search(num_ + r"\s*h(?:ours?)?\s+before\s+(?:the\s+)?(?:market\s+)?close", s))
            m_move = re.fullmatch(r"(?:after_)?move[_:\s-]*" + num_ + r"\s*c(?:ents?)?[_:\s-]*" + num_ + r"\s*" + unit, s)
            m_move2 = re.search(num_ + r"\s*" + unit + r"\s+after\s+(?:an?\s+)?" + num_ + r"\s*c(?:ents?)?\s+(?:price\s+)?(?:move|jump)", s)
            m_spread = re.fullmatch(r"(?:wide_)?spread[_:\s-]*" + num_ + r"\s*c(?:ents?)?", s)
            m_end = re.fullmatch(r"program_end[_:\s-]*" + num_ + r"\s*(m|min|minutes?)", s)
            if m_move:
                d = {"type": "after_move", "cents": float(m_move.group(1)),
                     "minutes": float(m_move.group(2)) * (60 if m_move.group(3).startswith("h") else 1)}
            elif m_move2:
                d = {"type": "after_move", "cents": float(m_move2.group(3)),
                     "minutes": float(m_move2.group(1)) * (60 if m_move2.group(2).startswith("h") else 1)}
            elif m_close:
                d = {"type": "before_close", "hours": float(m_close.group(1))}
            elif m_spread:
                d = {"type": "wide_spread", "cents": float(m_spread.group(1))}
            elif m_end:
                d = {"type": "program_end", "minutes": float(m_end.group(1))}
        if d is None:
            probs.append(f"pause rule not understood: {str(r)[:60]}")
        else:
            out.append(d)
    return out, probs


def _status_ok(s) -> bool:
    w = re.split(r"[\s:;,.-]+", str(s or "").strip().lower())
    return bool(w) and w[0] in ALLOWED_STATUS


def validate_plan(raw) -> tuple:
    """(plan, problems). A plan with any problem cannot be armed. Caps above the code's hard ceilings are problems, not clamps."""
    probs = []
    if not isinstance(raw, dict):
        return None, ["the plan file is not a JSON object"]
    if raw.get("version") != 1:
        probs.append(f"plan version {raw.get('version')!r}: this executor reads version 1")
    if str(raw.get("strategy") or "") != "rewards_maker":
        probs.append(f"strategy {raw.get('strategy')!r}: this executor runs rewards_maker plans")
    if not _status_ok(raw.get("status")):
        probs.append(f"the plan's status is {str(raw.get('status'))[:40]!r}: only proposal / approved / ready / live can go live")
    caps = {}
    for k in ("capital_cap_usd", "per_market_cap_usd", "daily_loss_stop_usd", "max_open_orders"):
        v = _f(raw.get(k))
        if v is None or v <= 0:
            probs.append(f"{k} missing or not above 0")
            continue
        if v > HARD[k]:
            probs.append(f"{k} = {v:g} is above the code's ceiling {HARD[k]:g}")
        caps[k] = int(v) if k == "max_open_orders" else round(v, 2)
    if caps.get("per_market_cap_usd") and caps.get("capital_cap_usd") and caps["per_market_cap_usd"] > caps["capital_cap_usd"]:
        probs.append("per_market_cap_usd is above capital_cap_usd")
    mk = []
    for i, m in enumerate(raw.get("markets") or []):
        if not isinstance(m, dict):
            probs.append(f"market #{i + 1} is not an object")
            continue
        s = str(m.get("series") or "")
        if not TICKER_RX.fullmatch(s):
            probs.append(f"market #{i + 1}: series {s[:30]!r} is not a Kalshi series ticker")
            continue
        q = m.get("quote") if isinstance(m.get("quote"), dict) else {}
        off, size = _f(q.get("offset_cents"), 0.0), _f(q.get("size"))
        if off is None or off < 0 or off > HARD["offset_cents"] or off != int(off):
            probs.append(f"{s}: offset_cents must be a whole number 0-{HARD['offset_cents']}")
            continue
        if size is None or size < 1 or size != int(size) or size > HARD["size"]:
            probs.append(f"{s}: quote size must be a whole number 1-{HARD['size']}")
            continue
        pz, pp = parse_pause(m.get("pause") if isinstance(m.get("pause"), list) else ([m["pause"]] if m.get("pause") else []))
        tick = [str(t) for t in (m.get("tickers") or []) if TICKER_RX.fullmatch(str(t))]
        mm = _f(m.get("max_markets"), 2)
        anchor = str(q.get("anchor") or "reference").lower()
        mk.append({"series": s, "why": str(m.get("why") or "")[:160], "offset_cents": int(off), "size": int(size), "pause": pz,
                   "pause_problems": pp, "tickers": tick, "max_markets": max(1, min(int(mm or 2), HARD["markets"])),
                   "anchor": anchor if anchor in ("reference", "best_bid") else "reference"})
    if not mk:
        probs.append("the plan lists no market")
    if sum(m["max_markets"] for m in mk) > HARD["markets"]:
        probs.append(f"the plan quotes more than {HARD['markets']} markets")
    plan = {"version": 1, "strategy": "rewards_maker", "status": str(raw.get("status") or "")[:60], "caps": caps, "markets": mk,
            "unproven": [str(x)[:200] for x in (raw.get("unproven") or [])][:8], "evidence": raw.get("evidence") or {},
            "date": str(raw.get("date") or raw.get("updated") or "")[:20]}
    return plan, probs


def norm_candidate(raw, name="") -> tuple:
    """(candidate, why-not). A runnable taker candidate: status allowed, strategy taker-like, series, price_band [lo, hi],
    decide_hours_before_close, size_usd_per_bet (<= the ceiling). Anything else is listed but never traded."""
    if not isinstance(raw, dict):
        return None, "not a JSON object"
    if not _status_ok(raw.get("status")):
        return None, f"status {str(raw.get('status'))[:30]!r} (only proposal / approved / ready / live)"
    rule = raw.get("rule") if isinstance(raw.get("rule"), dict) else {}
    g = lambda k, d=None: raw.get(k, rule.get(k, d))  # noqa: E731
    strat = str(raw.get("strategy") or rule.get("type") or "").lower()
    if not any(w in strat for w in ("taker", "fav", "band", "late")):
        return None, f"strategy {strat[:30]!r} is not a taker rule this executor runs"
    rules = [r for r in (raw.get("rules") or []) if isinstance(r, dict)]
    series = raw.get("series") if isinstance(raw.get("series"), list) else ([raw["series"]] if raw.get("series") else [])
    hours_default = _f(g("decide_hours_before_close"))
    per = [{"series": str(r.get("series")), "hours": _f(r.get("decide_hours_before_close"), hours_default)} for r in rules]
    per += [{"series": str(s), "hours": hours_default} for s in series]
    per = [p for p in per if TICKER_RX.fullmatch(p["series"]) and p["hours"] and 0 < p["hours"] <= 72]
    band = g("price_band")
    try:
        lo, hi = float(band[0]), float(band[1])
    except (TypeError, ValueError, IndexError, KeyError):
        return None, "no price_band [low, high]"
    usd = _f(g("size_usd_per_bet"))
    if not per:
        return None, "no series with decide_hours_before_close"
    if not (MIN_PX <= lo < hi <= MAX_PX):
        return None, f"price_band {lo}-{hi} outside 0.02-0.98"
    if not usd or usd <= 0 or usd > HARD["size_usd_per_bet"]:
        return None, f"size_usd_per_bet must be above 0 and at most {HARD['size_usd_per_bet']:g}"
    return {"name": name or str(raw.get("name") or "")[:60], "rules": per, "band": (lo, hi), "usd": usd,
            "max_spread": _f(g("max_spread"), 0.06), "status": str(raw.get("status"))[:40]}, ""


CLOCK_PATH = None            # None = engine/kalshi_clock.CFG_PATH (research/lab/kalshi_clock.json); tests point it elsewhere


def load_all(plan_path=None, cand_dir=None, state_dir=None) -> dict:
    """The maker plan + the taker candidates + the K8 clock settings (engine/kalshi_clock.py, with the bet size picked on the phone)
    and ONE hash over them (what the owner arms: any change = OFF until the phrase is typed again). Never raises."""
    plan_path, cand_dir = plan_path or PLAN_PATH, cand_dir or CAND_DIR
    out = {"plan": None, "problems": [], "cands": [], "skipped": [], "sha": "", "has_plan": os.path.isfile(plan_path)}
    h = hashlib.sha256()
    raw = _jread(plan_path, None) if out["has_plan"] else None
    if out["has_plan"]:
        try:
            with open(plan_path, "rb") as fh:
                h.update(b"plan\0" + fh.read())
        except OSError:
            pass
        plan, probs = validate_plan(raw)
        out["plan"], out["problems"] = plan, probs
    for fn in sorted(glob.glob(os.path.join(cand_dir, "*.json"))):
        name = os.path.splitext(os.path.basename(fn))[0]
        try:
            with open(fn, "rb") as fh:
                data = fh.read()
            c, why = norm_candidate(json.loads(data.decode("utf-8")), name)
        except (OSError, ValueError):
            c, why = None, "unreadable"
        if c:
            h.update(b"cand\0" + name.encode() + b"\0" + data)
            out["cands"].append(c)
        else:
            out["skipped"].append(f"{name}: {why}")
    out["clock"], out["clock_problems"] = None, []
    try:
        from engine import kalshi_clock
        ccfg, cprobs = kalshi_clock.load_config(CLOCK_PATH, state_dir)
        out["clock"], out["clock_problems"] = ccfg, cprobs
        if ccfg["live_legs"] and not cprobs:
            h.update(b"clock\0" + json.dumps(ccfg, sort_keys=True).encode())
    except Exception as e:  # noqa: BLE001
        out["clock_problems"] = [f"the clock settings could not load ({e.__class__.__name__})"]
    out["clock_ok"] = bool(out["clock"] and out["clock"]["live_legs"] and not out["clock_problems"])
    h.update(EXEC_VERSION.encode())
    out["maker_runnable"] = bool((out["plan"] and not out["problems"]) or (not out["has_plan"] and out["cands"]))
    out["runnable"] = bool(out["maker_runnable"] or out["clock_ok"])
    out["sha"] = h.hexdigest() if out["runnable"] or out["plan"] or out["cands"] else ""
    out["caps"] = dict(DEFAULT_CAPS)
    out["caps"].update((out["plan"] or {}).get("caps") or {})
    out["caps"]["size"] = HARD["size"]
    return out


# ================================================================================================ arming (the typed phrase)
def _proof(sha, t) -> str:
    return hashlib.sha256(f"{sha}|{EXEC_VERSION}|{int(t)}|{PHRASE}".encode("utf-8")).hexdigest()


def arm_state(state_dir=None, sha=None, env=None, P=None) -> tuple:
    """(live?, why). Live only with the typed phrase's record for THIS plan + candidates and THIS executor version."""
    P = P or paths(state_dir)
    if off_by_env(env):
        return False, "switched off on this PC (LE_KALSHI_LIVE=0)"
    if os.path.exists(P["kill"]):
        return False, "the kill switch is on"
    rec = _jread(P["arm"], None)
    if not isinstance(rec, dict) or rec.get("armed") is not True:
        why = (rec or {}).get("stopped") if isinstance(rec, dict) else None
        return False, (f"stopped ({why}): type the phrase again" if why else "not armed (OFF is the default)")
    if rec.get("exec") != EXEC_VERSION:
        return False, "the executor was updated since you armed it: type the phrase again"
    if sha is not None and rec.get("sha") != sha:
        return False, "the plan changed since you armed it: type the phrase again"
    if rec.get("proof") != _proof(rec.get("sha"), rec.get("t") or 0):
        return False, "the live switch was not set with the phrase"
    return True, "armed by you on " + et_text(rec.get("t") or 0)


def arm(phrase, state_dir=None, plan_path=None, cand_dir=None, env=None, now=None, expect_sha=None) -> tuple:
    """The OWNER's step (KALSHI_LIVE.bat): only with the exact phrase. Clears the kill switch and any old stop. -> (ok, words)."""
    now = time.time() if now is None else now
    P = paths(state_dir)
    if off_by_env(env):
        return False, "not armed: LE_KALSHI_LIVE=0 switches Kalshi off on this PC"
    if str(phrase or "").strip() != PHRASE:
        return False, f"not armed: the phrase must be exactly: {PHRASE}"
    A = load_all(plan_path, cand_dir, state_dir)
    if A["clock_ok"] and not A["maker_runnable"]:
        try:
            from engine import kalshi_clock
            killed, kwhy = kalshi_clock.kill_state(state_dir, A["clock"])
        except Exception:  # noqa: BLE001
            killed, kwhy = False, ""
        if killed:
            return False, "not armed: " + kwhy + " (ask Claude before any restart)"
    if not A["runnable"]:
        why = "; ".join((A["problems"] + A["clock_problems"])[:3]) or "no plan file (research/lab/kalshi_live_plan.json) and no candidate"
        return False, "not armed: " + why
    if expect_sha is not None and A["sha"] != expect_sha:
        return False, "not armed: the plan changed while you were reading it: double-click KALSHI_LIVE.bat again"
    st0 = load_state(P)
    if st0.get("day") == et_day(now) and _f(st0.get("day_pnl"), 0.0) <= -A["caps"]["daily_loss_stop_usd"] + 1e-9:
        return False, "not armed: today's loss stop is already reached (ET day): try again tomorrow"
    os.makedirs(P["dir"], exist_ok=True)
    try:
        os.remove(P["kill"])
    except OSError:
        pass
    _jwrite(P["control"], {"cmds": []})                    # an old PAUSE / FLATTEN / KILL never replays into a fresh arm
    _jwrite(P["arm"], {"armed": True, "t": int(now), "day": et_day(now), "sha": A["sha"], "exec": EXEC_VERSION,
                       "proof": _proof(A["sha"], int(now)), "by": "pc"})
    st = load_state(P)
    st.pop("stopped", None)
    st["paused_until"] = None
    st["armed_t"] = int(now)
    save_state(P, st)
    log(P, {"t": int(now), "ev": "armed", "sha": A["sha"][:12]})
    return True, "armed"


def disarm(P, why, now=None):
    now = time.time() if now is None else now
    rec = _jread(P["arm"], {}) or {}
    _jwrite(P["arm"], {"armed": False, "t": int(now), "stopped": str(why)[:160], "was": rec.get("t")})


# ================================================================================================ state
def blank_state() -> dict:
    return {"v": 1, "day": None, "t": 0, "orders": {}, "seen_fills": [], "seen_settle": [], "cash": 0.0, "p_start": {}, "m_start": {},
            "marks": {}, "fills_today": 0, "fees_today": 0.0, "order_times": [], "orders_today": 0, "paused_until": None,
            "mids": {}, "progs": {}, "picked": {}, "alerts": {"day": None, "n": 0, "fill_n": 0, "last_fill": 0, "pending": []},
            "err_since": None, "rejects": 0, "mismatch": 0, "done_cmds": [], "taker_done": {}, "balance0": None, "last": {},
            "fill_net": {}, "settled": {}, "day_pnl": 0.0}


def load_state(P) -> dict:
    st = _jread(P["state"], None)
    b = blank_state()
    if isinstance(st, dict) and st.get("v") == 1:
        b.update(st)
    return b


def save_state(P, st):
    try:
        _jwrite(P["state"], st)
    except Exception:  # noqa: BLE001
        pass


# ================================================================================================ book maths (pure)
def ref_price(levels, target):
    """Kalshi liquidity rewards: walking down from the best bid, the first price where the size reaches Target / 5."""
    cum = 0.0
    for p, q in levels:
        cum += q
        if cum >= target / 5.0 - 1e-9:
            return p
    return None


def tick_of(mkt, p) -> float:
    for a, b, s in (mkt or {}).get("steps") or []:
        if a - 1e-9 <= p <= b + 1e-9 and s:
            return s
    return 0.01


def snap(p, step, down=True) -> float:
    k = p / step
    k = math.floor(k + 1e-9) if down else math.ceil(k - 1e-9)
    return round(k * step, 4)


def order_cost(o) -> float:
    n, p = int(o["count"]), float(o["price"])
    return round(n * (p if o["book"] == "bid" else 1 - p), 4)


def _mark(yes, no, mkt=None, last=None):
    if mkt and mkt.get("result") in ("yes", "no"):
        return 1.0 if mkt["result"] == "yes" else 0.0
    bid = yes[0][0] if yes else None
    ask = (1 - no[0][0]) if no else None
    if bid is not None and ask is not None:
        return round((bid + ask) / 2, 4)
    return bid if bid is not None else ask if ask is not None else last


# ================================================================================================ the gate before EVERY order (pure)
def used_market(v, t) -> float:
    rest = sum(order_cost({"count": max(int(round(o["remaining"])), 0), "price": o["price"], "book": o["book"]})
               for o in v["resting"] if o.get("ticker") == t and o.get("price") is not None and o.get("book") in ("bid", "ask"))
    return round(rest + (v["exposure"].get(t) or 0.0), 4)


def used_total(v) -> float:
    rest = sum(order_cost({"count": max(int(round(o["remaining"])), 0), "price": o["price"], "book": o["book"]})
               for o in v["resting"] if o.get("price") is not None and o.get("book") in ("bid", "ask"))
    return round(rest + sum(v["exposure"].values()), 4)


def check_order(o, v) -> tuple:
    """(True, 'OK', '') or (False, CODE, plain words). Every cap, every time, before an order can reach Kalshi."""
    def no(code, words=None):
        return False, code, words or PLAIN.get(code, code)
    try:
        now = v["now"]
        kind = o.get("kind")
        if kind not in ("quote", "taker", "flatten"):
            return no("BAD_ORDER", "unknown order kind")
        t, book, n, p = str(o.get("ticker") or ""), o.get("book"), o.get("count"), _f(o.get("price"))
        if not TICKER_RX.fullmatch(t) or book not in ("bid", "ask") or not isinstance(n, int) or isinstance(n, bool) or n < 1 or p is None:
            return no("BAD_ORDER")
        if kind == "flatten":                       # only ever makes Kalshi hold less; allowed when stopped / paused / killed
            pos = _f(v["pos"].get(t), 0.0)
            if o.get("reduce_only") is not True or o.get("tif") != "immediate_or_cancel" or o.get("post_only"):
                return no("BAD_ORDER", "a closing order must be reduce-only and immediate-or-cancel")
            if pos == 0 or (pos > 0 and book != "ask") or (pos < 0 and book != "bid") or n > abs(pos) + 1e-9:
                return no("NOT_HELD")
            if not 0.01 - 1e-9 <= p <= 0.99 + 1e-9:
                return no("PRICE", "price outside 1c-99c")
            return True, "OK", ""
        if v.get("kill"):
            return no("KILL")
        if not v.get("live"):
            return no("NOT_ARMED", v.get("why_not_live") or None)
        if v.get("stopped"):
            return no("STOPPED")
        if v.get("paused"):
            return no("PAUSED")
        if kind == "quote":
            exp = _f(o.get("expires"))
            if o.get("post_only") is not True or o.get("tif") != "good_till_canceled" or o.get("reduce_only"):
                return no("NOT_MAKER")
            if exp is None or exp <= now or exp > now + ORDER_TTL_S + 120:
                return no("EXPIRY")
        else:
            lo, hi = (o.get("band") or (None, None))
            if o.get("tif") != "immediate_or_cancel" or o.get("post_only") or o.get("reduce_only"):
                return no("BAD_ORDER", "a taker order must be a plain immediate-or-cancel limit")
            yes_px = p if book == "bid" else 1 - p          # the side's own price
            if lo is None or not (lo - 1e-9 <= yes_px <= hi + 1e-9):
                return no("BAND")
        if not (MIN_PX - 1e-9 <= p <= MAX_PX + 1e-9):
            return no("PRICE")
        caps = v["caps"]
        if n > min(int(caps.get("size") or HARD["size"]), HARD["size"]):
            return no("SIZE", f"more than {min(int(caps.get('size') or HARD['size']), HARD['size'])} contracts in one order")
        mk = v["markets"].get(t) or {}
        if mk.get("status") != "active" or (mk.get("close_ts") or 0) <= now + 60:
            return no("MARKET_CLOSED")
        b = v["books"].get(t)
        if not b or now - b["t"] > BOOK_MAX_AGE_S:
            return no("STALE_BOOK", f"the prices are more than {BOOK_MAX_AGE_S} s old")
        best_bid = b["yes"][0][0] if b["yes"] else None
        best_ask = round(1 - b["no"][0][0], 4) if b["no"] else None
        if kind == "quote" and ((book == "bid" and best_ask is not None and p >= best_ask - 1e-9)
                                or (book == "ask" and best_bid is not None and p <= best_bid + 1e-9)):
            return no("CROSS", "it would cross the book (take instead of rest)")
        cost = order_cost(o)
        um = used_market(v, t)
        if um + cost > caps["per_market_cap_usd"] + 1e-9:
            return no("MARKET_CAP", f"it would put {money(um + cost)} in this market (cap {money(caps['per_market_cap_usd'])})")
        ut = used_total(v)
        if ut + cost > caps["capital_cap_usd"] + 1e-9:
            return no("CAPITAL_CAP", f"it would put {money(ut + cost)} on Kalshi in total (cap {money(caps['capital_cap_usd'])})")
        if cost > (_f(v.get("balance"), 0.0)) + 1e-9:
            return no("BALANCE")
        if int(v.get("open_orders") or 0) + 1 > int(caps["max_open_orders"]):
            return no("OPEN_ORDERS", f"{v.get('open_orders')} orders already resting (max {caps['max_open_orders']})")
        room = caps["daily_loss_stop_usd"] + _f(v.get("day_pnl"), 0.0)
        if room <= 1e-9:
            return no("DAY_STOP")
        if cost > room + 1e-9:
            return no("STOP_ROOM", f"it could lose {money(cost)}, more than the {money(room)} left before today's stop")
        if int(v.get("orders_last_min") or 0) >= MAX_ORDERS_MIN:
            return no("RATE")
        if int(v.get("orders_today") or 0) >= MAX_ORDERS_DAY:
            return no("DAY_ORDERS")
        return True, "OK", ""
    except Exception as e:  # noqa: BLE001
        return no("ERROR", f"the check hit an error ({e.__class__.__name__}): blocked to be safe")


# ================================================================================================ the strategies (pure)
def move_paused(hist, now, rule) -> bool:
    lo = [m for t, m in hist or [] if now - t <= rule["minutes"] * 60 + 1e-9]
    return bool(lo) and (max(lo) - min(lo)) >= rule["cents"] / 100.0 - 1e-9


def rewards_orders(entry, prog, mkt, yes, no, now, hist=None) -> tuple:
    """Desired quotes for one rewarded market -> (orders, why none / ''). Sizes are the plan's; the caps shrink them later."""
    t = mkt.get("ticker")
    if entry.get("pause_problems"):
        return [], entry["pause_problems"][0]
    if mkt.get("status") != "active":
        return [], "market not open"
    close_h = max([DEFAULT_CLOSE_H] + [r["hours"] for r in entry["pause"] if r["type"] == "before_close"])
    if (mkt.get("close_ts") or 0) - now < close_h * 3600:
        return [], f"closes within {close_h:g} h"
    pend = max([PROGRAM_END_S] + [r["minutes"] * 60 for r in entry["pause"] if r["type"] == "program_end"])
    if (prog.get("end") or 0) - now < pend:
        return [], "the reward program ends soon"
    if (prog.get("start") or 0) > now:
        return [], "the reward program has not started"
    if not yes or not no:
        return [], "one side of the book is empty"
    best_bid, best_ask = yes[0][0], round(1 - no[0][0], 4)
    spread = best_ask - best_bid
    wide = min([WIDE_SPREAD] + [r["cents"] / 100.0 for r in entry["pause"] if r["type"] == "wide_spread"])
    if spread > wide + 1e-9:
        return [], f"spread {spread * 100:.0f}c is wider than {wide * 100:.0f}c"
    for r in entry["pause"]:
        if r["type"] == "after_move" and move_paused(hist, now, r):
            return [], f"paused: the price moved {r['cents']:g}c+ in the last {r['minutes']:g} min"
    off, size, target = entry["offset_cents"] / 100.0, int(entry["size"]), _f(prog.get("target"), 0.0)
    if entry.get("anchor") == "best_bid":
        ry, rn = best_bid, no[0][0]
    else:
        ry, rn = ref_price(yes, target), ref_price(no, target)
    out = []
    exp = int(now + ORDER_TTL_S)
    base = {"ticker": t, "count": size, "kind": "quote", "post_only": True, "tif": "good_till_canceled", "expires": exp}
    if ry is not None:
        p = snap(ry - off, tick_of(mkt, ry))
        if MIN_PX - 1e-9 <= p < best_ask - 1e-9:
            out.append(dict(base, book="bid", price=p))
    if rn is not None:
        q = snap(rn - off, tick_of(mkt, 1 - rn))
        p = round(1 - q, 4)
        if q >= MIN_PX - 1e-9 and p > best_bid + 1e-9:
            out.append(dict(base, book="ask", price=p))
    return out, "" if out else "no price left after the offset"


def taker_orders(c, mkt, yes, no, now, done) -> tuple:
    """One limit immediate-or-cancel order for a taker candidate's market, or (None, why)."""
    t = mkt.get("ticker")
    if t in done:
        return None, "already bet on this market"
    if mkt.get("status") != "active" or not mkt.get("close_ts"):
        return None, "market not open"
    rule = next((r for r in c["rules"] if t.upper().startswith(r["series"].upper())), None)
    if not rule:
        return None, "not this rule's series"
    left = mkt["close_ts"] - now
    if not (60 < left <= rule["hours"] * 3600):
        return None, "outside the decide window"
    if not yes or not no:
        return None, "one side of the book is empty"
    bid, ask = yes[0][0], round(1 - no[0][0], 4)
    if ask - bid > c["max_spread"] + 1e-9:
        return None, "spread too wide"
    lo, hi = c["band"]
    pick = None
    if lo <= ask <= hi:
        pick = ("bid", ask, ask)                            # buy YES at the YES ask
    if lo <= 1 - bid <= hi and (pick is None or 1 - bid > ask):
        pick = ("ask", bid, round(1 - bid, 4))              # buy NO = sell YES at the YES bid; NO costs 1 - bid
    if not pick:
        return None, "no side in the price band"
    book, price, side_px = pick
    n = int(c["usd"] // side_px)
    if n < 1:
        return None, "the bet size buys no contract"
    return {"ticker": t, "book": book, "price": round(price, 4), "count": n, "kind": "taker", "tif": "immediate_or_cancel",
            "post_only": False, "band": c["band"], "cand": c["name"]}, ""


# ================================================================================================ the executor
def _default_poster(base, topic, msg) -> bool:
    try:
        from engine import notify
        return bool(notify._post(base, topic, msg))
    except Exception:  # noqa: BLE001
        return False


class Executor:
    """One instance per loop process. cycle() = reconcile -> stops -> quotes. Writes only data/kalshi_live/ (or state_dir)."""

    def __init__(self, api, state_dir=None, plan_path=None, cand_dir=None, env=None, clock=time.time, poster=None, alert_cfg=None,
                 say=None, dry=False):
        self.api, self.P, self.env, self.clock, self.dry = api, paths(state_dir), (os.environ if env is None else env), clock, dry
        self.plan_path, self.cand_dir = plan_path or PLAN_PATH, cand_dir or CAND_DIR
        self.poster = poster or _default_poster
        self._alert = alert_cfg
        self.say = say or (lambda *_: None)
        self.st = blank_state() if dry else load_state(self.P)
        self.A = load_all(self.plan_path, self.cand_dir, self.P["dir"] if state_dir else None)
        self.done, self.stop_why = False, None
        self.v = None
        self.pick_now, self.cand_mk = {}, {}

    def _log(self, row):
        if not self.dry:
            log(self.P, row)

    # ------------------------------------------------------------------ alerts (few: see the module docstring)
    def alert_cfg(self) -> dict:
        if self._alert is None:
            try:
                from engine import notify
                self._alert = notify.alert_cfg(self.env)
            except Exception:  # noqa: BLE001
                self._alert = {}
        return self._alert or {}

    def push(self, kind, title, body, priority="default", tags="moneybag", now=None) -> bool:
        if self.dry:
            return False
        now = self.clock() if now is None else now
        a = self.st.setdefault("alerts", blank_state()["alerts"])
        day = et_day(now)
        if a.get("day") != day:
            a.update({"day": day, "n": 0, "fill_n": 0})
        if kind != "stop" and int(a.get("n") or 0) >= PUSH_DAY_MAX:
            self._log({"t": int(now), "ev": "push_skipped", "kind": kind, "why": "day budget used"})
            return False
        cfg = self.alert_cfg()
        if not cfg.get("topic"):
            self._log({"t": int(now), "ev": "push_skipped", "kind": kind, "why": "no private alert topic"})
            return False
        try:
            from engine import notify
            quiet = notify.quiet(now)
        except Exception:  # noqa: BLE001
            quiet = False
        if quiet and kind != "stop":
            priority = "low"
        msg = {"title": title.encode("ascii", "replace").decode("ascii")[:120], "body": body[:900], "priority": priority, "tags": tags}
        try:
            ok = bool(self.poster(cfg.get("ntfy") or "https://ntfy.sh", cfg["topic"], msg))
        except Exception:  # noqa: BLE001
            ok = False
        if ok and kind != "stop":
            a["n"] = int(a.get("n") or 0) + 1
        a.setdefault("sent", []).append([int(now), kind])
        a["sent"] = a["sent"][-60:]
        self._log({"t": int(now), "ev": "push", "kind": kind, "ok": ok, "title": msg["title"]})
        return ok

    def flush_fills(self, now, force=False):
        a = self.st["alerts"]
        pend = a.get("pending") or []
        if not pend:
            return False
        if et_day(now) != a.get("day"):
            a.update({"day": et_day(now), "n": 0, "fill_n": 0})
        if not force and int(a.get("fill_n") or 0) >= FILL_PUSH_DAY_MAX:
            a["pending"] = []                       # today's fill pushes are used: the rest are in the day summary only
            return False
        if not force and now - float(a.get("last_fill") or 0) < FILL_PUSH_GAP_S:
            return False
        lines = [x["w"] for x in pend[:6]] + ([f"... and {len(pend) - 6} more"] if len(pend) > 6 else [])
        v = self.v or {}
        title = f"Kalshi: {len(pend)} fill{'s' if len(pend) != 1 else ''} | day {money(v.get('day_pnl', 0), True)}"
        body = "; ".join(lines) + f". In use {money(used_total(v) if v else 0)} of {money(self.A['caps']['capital_cap_usd'])}."
        if self.push("fill", title, body, priority="default", tags="moneybag", now=now):
            a["fill_n"] = int(a.get("fill_n") or 0) + 1
            a["last_fill"] = now
            a["pending"] = []
            return True
        if int(a.get("n") or 0) >= PUSH_DAY_MAX or int(a.get("fill_n") or 0) >= FILL_PUSH_DAY_MAX:
            a["pending"] = []                       # the day's budget is used: the fills go to the day summary only
        return False

    # ------------------------------------------------------------------ commands from the phone / the PC
    def controls(self, now):
        c = _jread(self.P["control"], {}) or {}
        done = set(self.st.get("done_cmds") or [])
        for cmd in c.get("cmds") or []:
            cid = str(cmd.get("id") or "")
            if not cid or cid in done:
                continue
            done.add(cid)
            what = cmd.get("cmd")
            self._log({"t": int(now), "ev": "command", "cmd": what, "src": cmd.get("src")})
            if what == "pause":
                self.st["paused_until"] = float(cmd.get("until") or next_4pm(now))
                self.cancel_all(scope="ours", now=now)
            elif what == "resume":
                self.st["paused_until"] = None
            elif what == "flatten":
                self.stop("FLATTEN pressed (" + str(cmd.get("src") or "pc") + ")", scope="all", flatten=True, now=now)
            elif what == "kill":
                self.stop("KILL pressed (" + str(cmd.get("src") or "pc") + ")", scope="all", flatten=bool(cmd.get("flatten")), kill=True, now=now)
            if self.done:
                break
        self.st["done_cmds"] = sorted(done)[-50:]

    # ------------------------------------------------------------------ cancel / flatten / stop
    def _resting(self):
        return [norm_order(o) for o in self.api.pages("/portfolio/orders", "orders", {"status": "resting", "limit": 1000})]

    def cancel(self, o) -> bool:
        try:
            self.api.call("DELETE", "/portfolio/events/orders/" + o["id"], {"market_ticker": o.get("ticker")})
            ok = True
        except KalshiError as e:
            ok = e.status == 404                    # already gone
            self._log({"t": int(self.clock()), "ev": "cancel_failed", "why": str(e)[:200]})
        self.st["orders"].pop(o["id"], None)
        if self.v is not None:
            self.v["resting"] = [x for x in self.v["resting"] if x["id"] != o["id"]]
            self.v["open_orders"] = len(self.v["resting"])
        return ok

    def cancel_all(self, scope="ours", now=None) -> dict:
        """Cancel every resting order of ours (or of the whole account), in batches of 20, then check. -> {cancelled, left}."""
        now = self.clock() if now is None else now
        try:
            rest = self._resting()
        except KalshiError as e:
            self._log({"t": int(now), "ev": "cancel_all_failed", "why": str(e)[:200]})
            return {"cancelled": 0, "left": None, "error": str(e)[:160]}
        todo = [o for o in rest if o["id"] and (scope == "all" or o["coid"].startswith(COID))]
        n = 0
        for i in range(0, len(todo), 20):
            chunk = todo[i:i + 20]
            try:
                r = self.api.call("DELETE", "/portfolio/events/orders/batched",
                                  body={"orders": [{"order_id": o["id"], "market_ticker": o["ticker"]} for o in chunk]})
                bad = {str(x.get("order_id")) for x in (r.get("orders") or []) if isinstance(x, dict) and x.get("error")}
                n += len(chunk) - len(bad)
                for o in chunk:
                    if o["id"] in bad:
                        n += self.cancel(o)
                    else:
                        self.st["orders"].pop(o["id"], None)
            except KalshiError:
                for o in chunk:
                    n += self.cancel(o)
        try:
            left = len([o for o in self._resting() if scope == "all" or o["coid"].startswith(COID)])
        except KalshiError:
            left = None
        if self.v is not None:
            self.v["resting"] = [] if scope == "all" else [x for x in self.v["resting"] if not x["coid"].startswith(COID)]
            self.v["open_orders"] = len(self.v["resting"])
        self._log({"t": int(now), "ev": "cancel_all", "scope": scope, "cancelled": n, "left": left})
        return {"cancelled": n, "left": left}

    def flatten_all(self, now=None) -> dict:
        """Sell what Kalshi holds at the best price (reduce-only, immediate-or-cancel). -> {sold: markets, left: markets}."""
        now = self.clock() if now is None else now
        try:
            pos = norm_positions(self.api.pages("/portfolio/positions", "market_positions", {"count_filter": "position", "limit": 1000}))
        except KalshiError as e:
            return {"sold": 0, "left": None, "error": str(e)[:160]}
        sold = 0
        for t, p in pos.items():
            n = int(round(abs(p["pos"])))
            if n < 1:
                continue
            try:
                yes, no = norm_book(self.api.get(f"/markets/{t}/orderbook", auth=False))
            except KalshiError:
                continue
            if p["pos"] > 0 and yes:
                o = {"ticker": t, "book": "ask", "price": yes[0][0], "count": n}
            elif p["pos"] < 0 and no:
                o = {"ticker": t, "book": "bid", "price": round(1 - no[0][0], 4), "count": n}
            else:
                continue
            o.update(kind="flatten", tif="immediate_or_cancel", reduce_only=True, post_only=False)
            ok, code, words = check_order(o, {"now": now, "pos": {t: p["pos"]}})
            if ok and self.send(o, now, check=False):
                sold += 1
        try:
            left = len([1 for p in norm_positions(self.api.pages("/portfolio/positions", "market_positions",
                                                                 {"count_filter": "position", "limit": 1000})).values() if abs(p["pos"]) >= 1])
        except KalshiError:
            left = None
        self._log({"t": int(now), "ev": "flatten", "sold": sold, "left": left})
        return {"sold": sold, "left": left}

    def stop(self, why, scope="ours", flatten=False, kill=False, now=None):
        """ANY stop: cancel, (flatten), OFF (re-arm needs the phrase), one push at once."""
        now = self.clock() if now is None else now
        if self.done:
            return
        self.done, self.stop_why = True, why
        c = self.cancel_all(scope=scope, now=now) if not self.dry else {"cancelled": 0, "left": 0}
        f = self.flatten_all(now=now) if flatten and not self.dry else None
        if kill:
            try:
                os.makedirs(self.P["dir"], exist_ok=True)
                with open(self.P["kill"], "w", encoding="utf-8") as fh:
                    fh.write(f"{int(now)} {why}\n")
            except OSError:
                pass
        disarm(self.P, why, now)
        self.st["stopped"] = {"t": int(now), "why": str(why)[:160]}
        v = self.v or {}
        parts = [f"Day {money(v.get('day_pnl', 0), True)} (stop -{money(self.A['caps']['daily_loss_stop_usd'])})." if v else ""]
        if c.get("left") is None:
            parts.append("Could NOT reach Kalshi to cancel: open the Kalshi app and cancel the resting orders by hand"
                         " (each one also expires by itself within 20 minutes).")
        elif c["left"]:
            parts.append(f"{c['left']} order(s) could not be cancelled: cancel them in the Kalshi app.")
        else:
            parts.append(f"All orders cancelled ({c['cancelled']}).")
        if f is not None:
            parts.append(f"Sold {f['sold']} position(s)" + (f", {f['left']} still held (thin book: sell in the app)." if f.get("left") else "."))
        held = [t for t, x in (v.get("pos") or {}).items() if abs(_f(x, 0)) >= 1] if f is None else []
        if held:
            parts.append(f"Holding {len(held)} market(s): they settle by themselves.")
        parts.append("OFF now: to restart, double-click KALSHI_LIVE.bat and type the phrase.")
        self.push("stop", f"Kalshi STOPPED: {why}"[:110], " ".join(p for p in parts if p), priority="high", tags="warning", now=now)
        self._log({"t": int(now), "ev": "stopped", "why": why, "scope": scope, "flatten": bool(flatten), "kill": bool(kill)})

    # ------------------------------------------------------------------ sending one order (always through check_order)
    def send(self, o, now, check=True) -> bool:
        if self.dry:
            return False
        if check:
            ok, code, words = check_order(o, self.v)
            if not ok:
                return False
        if o["kind"] != "flatten" and (os.path.exists(self.P["kill"]) or (_jread(self.P["arm"], {}) or {}).get("armed") is not True):
            return False                                   # a phone / PC stop landed in the middle of this loop
        coid = f"{COID}{int(now):x}-{secrets.token_hex(3)}"
        body = {"ticker": o["ticker"], "side": o["book"], "count": str(int(o["count"])), "price": f"{float(o['price']):.4f}",
                "time_in_force": o["tif"], "self_trade_prevention_type": "taker_at_cross", "client_order_id": coid}
        if o["kind"] == "quote":
            body.update(post_only=True, expiration_time=int(o["expires"]), cancel_order_on_pause=True)
        if o.get("reduce_only"):
            body["reduce_only"] = True
        try:
            r = self.api.call("POST", "/portfolio/events/orders", body=body)
        except KalshiError as e:
            self.st["order_times"] = (self.st.get("order_times") or [])[-200:] + [now]
            if e.status == 410 or e.code == "deprecated_v1_order_endpoint":
                self.stop("Kalshi changed its order API (410): Claude must update the executor", now=now)
            elif e.status == 401 or (e.status == 403 and "location" not in str(e).lower()):
                self.stop("Kalshi refused the key (" + str(e.status) + ")", now=now)
            elif e.code == "invalid_order" and "post only" in str(e).lower():
                self._log({"t": int(now), "ev": "cross", "ticker": o["ticker"]})      # the price moved: next loop requotes
            elif e.code in ("trading_is_paused", "exchange_is_paused", "market_inactive", "too_many_requests") or (e.status or 0) >= 500 \
                    or e.code in ("network", "context_canceled"):
                self._log({"t": int(now), "ev": "order_not_taken", "why": str(e)[:200]})
            else:
                self.st["rejects"] = int(self.st.get("rejects") or 0) + 1
                self._log({"t": int(now), "ev": "rejected", "why": str(e)[:200], "n": self.st["rejects"]})
                if self.st["rejects"] >= REJECT_STOP:
                    self.stop(f"Kalshi refused {self.st['rejects']} orders in a row ({e.code or e.status})", now=now)
            return False
        self.st["rejects"] = 0
        self.st["order_times"] = (self.st.get("order_times") or [])[-200:] + [now]
        self.st["orders_today"] = int(self.st.get("orders_today") or 0) + 1
        oid = str(r.get("order_id") or "")
        rem = _f(r.get("remaining_count"), _f(r.get("remaining_count_fp"), 0.0))
        rec = {"id": oid, "coid": coid, "ticker": o["ticker"], "book": o["book"], "price": float(o["price"]), "remaining": rem or 0.0,
               "exp": o.get("expires"), "t": int(now), "kind": o["kind"]}
        if o["kind"] == "quote" and oid and (rem or 0) > 0:
            self.st["orders"][oid] = rec
            if self.v is not None:
                self.v["resting"].append(dict(rec, status="resting"))
                self.v["open_orders"] = len(self.v["resting"])
        if self.v is not None:
            self.v["orders_last_min"] = int(self.v.get("orders_last_min") or 0) + 1
            self.v["orders_today"] = int(self.v.get("orders_today") or 0) + 1
        self._log({"t": int(now), "ev": "order", "kind": o["kind"], "ticker": o["ticker"], "book": o["book"], "price": o["price"],
                     "n": o["count"], "id": oid[-6:]})
        return True

    # ------------------------------------------------------------------ market data
    def programs(self, series, now) -> list:
        """Active liquidity-reward programs of a series (public, cached 10 min)."""
        c = self.st.setdefault("progs", {}).get(series)
        if c and now - c.get("t", 0) < PROG_REFRESH_S:
            return c["rows"]
        rows = []
        for x in self.api.pages("/incentive_programs", "incentive_programs",
                                {"status": "active", "type": "liquidity", "series_ticker": series, "limit": 1000}, max_pages=3, auth=False):
            if x.get("series_ticker") not in (None, series) or str(x.get("incentive_type") or "liquidity") != "liquidity":
                continue
            a, b = _ts(x.get("start_date")), _ts(x.get("end_date"))
            if not (a and b and x.get("market_ticker")):
                continue
            usd_day = (_f(x.get("period_reward"), 0.0) / 1e4) / max((b - a) / 86400.0, 1e-6)
            rows.append({"ticker": x["market_ticker"], "start": a, "end": b, "usd_day": round(usd_day, 2),
                         "target": _f(x.get("target_size_fp"), _f(x.get("target_size"), 0.0)) or 0.0})
        self.st["progs"][series] = {"t": now, "rows": rows}
        return rows

    def pick(self, entry, progs, now) -> list:
        """Up to max_markets rewarded markets of the series: the ones already quoted first (no churn), then the biggest pools."""
        live = [p for p in progs if p["start"] <= now < p["end"] - PROGRAM_END_S]
        if entry["tickers"]:
            live = [p for p in live if p["ticker"] in entry["tickers"]]
        live.sort(key=lambda p: (-p["usd_day"], p["ticker"]))
        before = set(self.st.setdefault("picked", {}).get(entry["series"]) or [])
        keep = [p for p in live if p["ticker"] in before]
        rest = [p for p in live if p["ticker"] not in before]
        out = (keep + rest)[: entry["max_markets"]]
        self.st["picked"][entry["series"]] = [p["ticker"] for p in out]
        return out

    def market_data(self, tickers, now) -> tuple:
        mk, bk = {}, {}
        for t in sorted(set(x for x in tickers if x)):
            try:
                m = norm_market(self.api.get(f"/markets/{t}", auth=False))
                m["ticker"] = m.get("ticker") or t
                yes, no = norm_book(self.api.get(f"/markets/{t}/orderbook", auth=False))
            except KalshiError as e:
                self._log({"t": int(now), "ev": "market_data_failed", "ticker": t, "why": str(e)[:160]})
                continue
            mk[t], bk[t] = m, {"t": self.clock(), "yes": yes, "no": no}
        return mk, bk

    def desired(self, now, mk, bk) -> tuple:
        """-> (orders, notes {ticker: why none}). The strategy part, shared by the loop and the dry run."""
        orders, notes = [], {}
        plan = self.A["plan"] if (self.A["plan"] and not self.A["problems"]) else None
        for entry in (plan or {}).get("markets") or []:
            if not self.pick_now.get(entry["series"]):
                notes[entry["series"]] = "no rewarded market open right now"
            for prog in self.pick_now.get(entry["series"], []):
                t = prog["ticker"]
                m, b = mk.get(t), bk.get(t)
                if not m or not b:
                    notes[t] = "no prices"
                    continue
                o, why = rewards_orders(entry, prog, m, b["yes"], b["no"], now, (self.st.get("mids") or {}).get(t))
                for x in o:
                    x["series"] = entry["series"]
                orders += o
                if why:
                    notes[t] = why
        for c in self.A["cands"]:
            for t in self.cand_mk.get(c["name"], []):
                m, b = mk.get(t), bk.get(t)
                if not m or not b:
                    continue
                o, why = taker_orders(c, m, b["yes"], b["no"], now, self.st.get("taker_done") or {})
                if o:
                    orders.append(o)
        return orders, notes

    def choose(self, now, say=None) -> list:
        """The markets to look at this loop: the plan's rewarded markets + the candidates' markets (public data)."""
        self.pick_now = {}
        plan = self.A["plan"] if (self.A["plan"] and not self.A["problems"]) else None
        for entry in (plan or {}).get("markets") or []:
            try:
                self.pick_now[entry["series"]] = self.pick(entry, self.programs(entry["series"], now), now)
            except KalshiError as e:
                self._log({"t": int(now), "ev": "programs_failed", "series": entry["series"], "why": str(e)[:160]})
                if say:
                    say(f"  [..] {entry['series']}: Kalshi did not answer ({str(e)[:80]})")
        self.cand_mk = self.candidate_markets(now) if self.A["cands"] else {}
        return [p["ticker"] for ps in self.pick_now.values() for p in ps] + [t for ts in self.cand_mk.values() for t in ts]

    def candidate_markets(self, now) -> dict:
        out = {}
        for c in self.A["cands"]:
            ts = []
            for r in c["rules"]:
                try:
                    rows = self.api.pages("/markets", "markets", {"series_ticker": r["series"], "status": "open", "limit": 200},
                                          max_pages=2, auth=False)
                except KalshiError:
                    continue
                for m in rows:
                    ct = _ts(m.get("close_time"))
                    if m.get("ticker") and ct and 60 < ct - now <= r["hours"] * 3600:
                        ts.append(m["ticker"])
            out[c["name"]] = sorted(set(ts))[:HARD["markets"]]
        return out

    # ------------------------------------------------------------------ one loop
    def view(self, now, bal, pos, rest, mk, bk, live, why_live) -> dict:
        caps = dict(self.A["caps"])
        times = [t for t in (self.st.get("order_times") or []) if now - t < 60]
        paused = bool(self.st.get("paused_until") and float(self.st["paused_until"]) > now)
        return {"now": now, "kill": os.path.exists(self.P["kill"]), "live": live, "why_not_live": why_live, "paused": paused,
                "stopped": bool(self.st.get("stopped")) or self.done, "caps": caps, "balance": bal, "resting": rest,
                "open_orders": len(rest), "exposure": {t: p["exposure"] for t, p in pos.items()},
                "pos": {t: p["pos"] for t, p in pos.items()}, "markets": mk, "books": bk, "day_pnl": 0.0,
                "orders_last_min": len(times), "orders_today": int(self.st.get("orders_today") or 0)}

    def cycle(self) -> dict:
        now = self.clock()
        try:
            out = self._cycle(now)
        except Exception as e:  # noqa: BLE001  (never raises into the loop runner; a crash-looping cycle stops below)
            out = {"error": f"{e.__class__.__name__}: {redact(e)}"}
            self._log({"t": int(now), "ev": "cycle_error", "why": out["error"]})
            self._failing(now, out["error"])
        self.st["t"] = now
        self.st["last"] = dict(self.st.get("last") or {}, **{k: out.get(k) for k in ("placed", "cancelled", "error", "note", "resting") if k in out})
        if not self.dry:
            save_state(self.P, self.st)
            write_card(self.P, self)
        return out

    def _failing(self, now, why):
        s = self.st.get("err_since") or now
        self.st["err_since"] = s
        if now - s >= FAIL_STOP_S:
            self.stop("Kalshi has not answered for 15 minutes", now=now)

    def _cycle(self, now) -> dict:
        st = self.st
        self.A = load_all(self.plan_path, self.cand_dir, self.P["dir"] if self.P["dir"] != STATE_DIR else None)   # every loop
        self.controls(now)
        if self.done:
            return {"note": "stopped by a command"}
        live, why = arm_state(sha=self.A["sha"], env=self.env, P=self.P)
        if not live:
            if off_by_env(self.env):
                self.stop("switched off on this PC (LE_KALSHI_LIVE=0)", now=now)
            elif os.path.exists(self.P["kill"]):
                self.stop("the kill switch is on", scope="all", now=now)
            elif st.get("armed_t") and not st.get("stopped"):
                said = str((_jread(self.P["arm"], {}) or {}).get("stopped") or "")
                hard = "FLATTEN" in said or "KILL" in said
                self.stop(why.replace(": type the phrase again", ""), scope="all" if hard else "ours", flatten=hard, now=now)
            else:
                self.done = True
            return {"note": why}
        if not self.A["maker_runnable"]:
            if self.A["plan"] and self.A["problems"] and st.get("armed_t"):
                self.stop("the plan has a problem: " + "; ".join(self.A["problems"][:2]), now=now)
            else:
                self.done = True                            # nothing for the maker loop (the K8 clock bets run in their own loop)
            return {"note": "no maker plan"}
        # 1. Kalshi first: exchange, cash, positions, resting orders, fills, settlements
        try:
            ex = self.api.get("/exchange/status", auth=False)
            trading = ex.get("trading_active", True) is not False and ex.get("exchange_active", True) is not False
        except KalshiError:
            trading = True                                  # unknown: Kalshi refuses orders itself while it pauses trading
        try:
            bal_j = self.api.get("/portfolio/balance")
            bal = _f(bal_j.get("balance_dollars"), (_f(bal_j.get("balance"), 0.0) or 0.0) / 100.0)
            pos = norm_positions(self.api.pages("/portfolio/positions", "market_positions", {"count_filter": "position", "limit": 1000}))
            rest = self._resting()
            since = int(min(float(st.get("day_t0") or now), now) - 120)
            fills = [norm_fill(f) for f in self.api.pages("/portfolio/fills", "fills", {"min_ts": since, "limit": 1000})]
            sets = [norm_settlement(s) for s in self.api.pages("/portfolio/settlements", "settlements", {"min_ts": since, "limit": 1000})]
        except KalshiError as e:
            if e.status == 401 or e.code in ("no_key", "bad_key", "key_in_repo"):
                self.stop("Kalshi refused the key" if e.status == 401 else str(e)[:120], now=now)
            else:
                self._failing(now, str(e))
            return {"error": str(e)[:200]}
        st["err_since"] = None
        # 2. a new ET day: the summary of the last one, a fresh start
        day = et_day(now)
        if st.get("day") != day:
            if st.get("day"):
                self.flush_fills(now, force=True)
                self.push("summary", f"Kalshi day {st['day']}: {money(st.get('day_pnl', 0), True)}",
                          f"{st.get('fills_today', 0)} fills, {money(st.get('fees_today', 0))} fees. Kalshi pays the liquidity rewards "
                          f"separately (not in this number). Resting now: {len([o for o in rest if o['coid'].startswith(COID)])} orders.",
                          priority="low", tags="bar_chart", now=now)
            st.update({"day": day, "day_t0": now, "cash": 0.0, "p_start": {t: p["pos"] for t, p in pos.items()}, "m_start": {},
                       "seen_fills": [f["id"] for f in fills], "seen_settle": [f"{s['ticker']}|{s['ts']}" for s in sets],
                       "fills_today": 0, "fees_today": 0.0, "orders_today": 0, "balance0": bal, "mismatch": 0, "fill_net": {}, "settled": {},
                       "day_pnl": 0.0,
                       "taker_done": {t: x for t, x in (st.get("taker_done") or {}).items() if now - float(x) < 7 * 86400}})
        # 3. which markets: the plan's rewarded markets, the candidates' markets, everything held or resting
        want = self.choose(now)
        mk, bk = self.market_data(want + list(pos) + [o["ticker"] for o in rest] + list(st.get("p_start") or {}), now)
        for t, b in bk.items():
            m = _mark(b["yes"], b["no"], mk.get(t), (st.get("marks") or {}).get(t))
            if m is not None:
                st.setdefault("marks", {})[t] = m
                st.setdefault("m_start", {}).setdefault(t, m)
                h = [x for x in (st.setdefault("mids", {}).get(t) or []) if now - x[0] <= 3 * 3600] + [[now, m]]
                st["mids"][t] = h[-200:]
        # 4. reconcile: today's fills and settlements -> cash and the expected positions; Kalshi's positions must match
        seen = set(st.get("seen_fills") or [])
        exp = {t: _f(x, 0.0) for t, x in (st.get("p_start") or {}).items()}
        for f in sorted(fills, key=lambda x: x["ts"] or 0):
            if not f["id"] or f["id"] in seen or (f["ts"] or 0) < float(st["day_t0"]) - 1 or f["book"] not in ("bid", "ask") or f["y"] is None:
                continue
            seen.add(f["id"])
            sgn = 1 if f["book"] == "bid" else -1
            fee = f["fee"] if f["fee"] is not None else fee_est(f["y"], f["n"], f["taker"])
            st["cash"] = round(float(st["cash"]) - sgn * f["n"] * f["y"] - fee, 6)
            st["fees_today"] = round(float(st.get("fees_today") or 0) + fee, 4)
            st["fills_today"] = int(st.get("fills_today") or 0) + 1
            st.setdefault("fill_net", {})[f["ticker"]] = _f(st.get("fill_net", {}).get(f["ticker"]), 0.0) + sgn * f["n"]
            word = (f"Bought {f['n']:g} YES at {f['y'] * 100:.0f}c" if sgn > 0 else f"Bought {f['n']:g} NO at {(1 - f['y']) * 100:.0f}c")
            name = (mk.get(f["ticker"]) or {}).get("title") or f["ticker"]
            if self.alert_cfg().get("topic"):
                st["alerts"]["pending"] = (st["alerts"].get("pending") or [])[-99:] + [{"t": f["ts"], "w": f"{word} - {str(name)[:40]}"}]
            for o in list(st["orders"].values()):
                if o["id"] == f["order_id"]:
                    o["remaining"] = max(0.0, float(o["remaining"]) - f["n"])
        st["seen_fills"] = sorted(seen)[-2000:]
        sseen = set(st.get("seen_settle") or [])
        for s in sets:
            k = f"{s['ticker']}|{s['ts']}"
            if k in sseen or (s["ts"] or 0) < float(st["day_t0"]) - 1:
                continue
            sseen.add(k)
            held = s["yes"] - s["no"]
            pay = 1.0 if s["result"] == "yes" else 0.0 if s["result"] == "no" else (s["value"] if s["value"] is not None else 0.0)
            st["cash"] = round(float(st["cash"]) + held * pay, 6)
            st.setdefault("settled", {})[s["ticker"]] = _f(st.get("settled", {}).get(s["ticker"]), 0.0) + held
        st["seen_settle"] = sorted(sseen)[-500:]
        for t in set(exp) | set(st.get("fill_net") or {}) | set(st.get("settled") or {}) | set(pos):
            exp[t] = exp.get(t, 0.0) + _f((st.get("fill_net") or {}).get(t), 0.0) - _f((st.get("settled") or {}).get(t), 0.0)
        bad = sorted(t for t in exp if abs(exp[t] - (pos.get(t) or {}).get("pos", 0.0)) >= 0.999)
        st["mismatch"] = int(st.get("mismatch") or 0) + 1 if bad else 0
        mine = {o["id"]: o for o in rest if o["coid"].startswith(COID)}
        for oid in list(st["orders"]):
            if oid not in mine:
                st["orders"].pop(oid, None)                 # filled, cancelled or expired (fills above tell which)
        for oid, o in mine.items():
            if oid not in st["orders"]:
                st["orders"][oid] = dict(o, t=int(now), kind="quote", adopted=True)
                self._log({"t": int(now), "ev": "adopted", "ticker": o["ticker"], "id": oid[-6:]})
            else:
                st["orders"][oid].update(remaining=o["remaining"], price=o["price"], exp=o["exp"] or st["orders"][oid].get("exp"))
        # 5. today's P&L (signed YES contracts at the mid) and the stops
        marks = st.get("marks") or {}
        value_now = sum(_f(p["pos"], 0.0) * _f(marks.get(t), 0.0) for t, p in pos.items())
        value_0 = sum(_f(x, 0.0) * _f((st.get("m_start") or {}).get(t), _f(marks.get(t), 0.0)) for t, x in (st.get("p_start") or {}).items())
        day_pnl = round(float(st["cash"]) + value_now - value_0, 4)
        st["day_pnl"] = day_pnl
        self.v = self.view(now, bal, pos, rest, mk, bk, live, why)
        self.v["day_pnl"] = day_pnl
        out = {"day_pnl": day_pnl, "resting": len(mine), "placed": 0, "cancelled": 0}
        caps = self.A["caps"]
        if st["mismatch"] >= MISMATCH_STOP:
            self.stop(f"Kalshi's positions do not match the fills ({', '.join(bad[:2])})", now=now)
            return out
        if day_pnl <= -caps["daily_loss_stop_usd"] + 1e-9:
            self.stop(f"daily loss stop: day {money(day_pnl, True)} (stop -{money(caps['daily_loss_stop_usd'])})", now=now)
            return out
        b0 = _f(st.get("balance0"))
        if b0 is not None and bal < b0 - caps["capital_cap_usd"] - caps["daily_loss_stop_usd"] - 0.01:
            self.stop(f"cash on Kalshi fell {money(b0 - bal)} today, more than the plan allows", now=now)
            return out
        self.flush_fills(now)
        # 6. quotes (not while paused or while Kalshi pauses trading)
        if self.v["paused"] or not trading:
            if mine:
                out["cancelled"] = self.cancel_all("ours", now)["cancelled"]
            out["note"] = "paused" if self.v["paused"] else "Kalshi trading is paused"
            return out
        want, notes = self.desired(now, mk, bk)
        keyed = {(o["ticker"], o["book"]): o for o in want if o["kind"] == "quote"}
        for oid, o in list(mine.items()):
            w = keyed.get((o["ticker"], o["book"]))
            exp_t = o.get("exp") or (st["orders"].get(oid) or {}).get("exp") or 0
            if w and abs((o["price"] or 0) - w["price"]) < 1e-9 and o["remaining"] >= 1 and exp_t - now > RENEW_BEFORE_S:
                keyed.pop((o["ticker"], o["book"]))           # keep it: same price, still resting, not about to expire
                continue
            out["cancelled"] += self.cancel(o)
            if self.done:
                return out
        for o in list(keyed.values()) + [x for x in want if x["kind"] == "taker"]:
            if self.done:
                break
            o = self.fit(o)
            if not o:
                continue
            ok, code, words = check_order(o, self.v)
            if not ok:
                notes[o["ticker"]] = words
                continue
            if self.send(o, now):
                out["placed"] += 1
                if o["kind"] == "taker":
                    st.setdefault("taker_done", {})[o["ticker"]] = int(now)
        out["notes"] = notes
        return out

    def fit(self, o):
        """Shrink a quote's contracts to the room the caps leave (the caps are still checked in full after)."""
        v, caps = self.v, self.A["caps"]
        per = o["price"] if o["book"] == "bid" else 1 - o["price"]
        if per <= 0:
            return None
        room = min(caps["per_market_cap_usd"] - used_market(v, o["ticker"]), caps["capital_cap_usd"] - used_total(v),
                   _f(v.get("balance"), 0.0), caps["daily_loss_stop_usd"] + v["day_pnl"])
        n = min(int(o["count"]), int(math.floor(room / per + 1e-9)))
        return dict(o, count=n) if n >= 1 else None


# ================================================================================================ the card, the phone, the PC hook
def card(P, ex=None, now=None) -> dict:
    now = time.time() if now is None else now
    st = ex.st if ex else load_state(P)
    live, why = arm_state(P=P, sha=(ex.A["sha"] if ex else None))
    caps = (ex.A if ex else load_all())["caps"]
    paused = bool(st.get("paused_until") and float(st["paused_until"]) > now)
    state = "live" if live and not paused else "paused" if live else "stopped" if st.get("stopped") else "off"
    c = {"kind": "kalshi_live_pub", "v": 1, "st": state, "u": iso(st.get("t") or now)}
    if state in ("live", "paused", "stopped"):
        c.update({"net": round(_f(st.get("day_pnl"), 0.0), 2), "f": int(st.get("fills_today") or 0), "o": len(st.get("orders") or {}),
                  "cap": caps["capital_cap_usd"], "stop": caps["daily_loss_stop_usd"]})
    if state == "stopped":
        c["why"] = re.sub(r"[^A-Za-z0-9 $+.,:()%-]", "", str((st.get("stopped") or {}).get("why") or ""))[:40]
    try:                                    # K8 clock bets (night-kalshi8): the phone's 'K8 status' block (engine/kalshi_clock.card_k8)
        from engine import kalshi_clock as KC
        k8 = KC.card_k8(P["dir"] if P["dir"] != STATE_DIR else None, now=now)
        if k8:
            c["k8"] = k8
            c["u"] = iso(now)
            # day-kalshi QA 2026-11-21: K8's own stop / pause (the clock writes arm.json + clock_state.json, not the maker's state):
            # a K8 that stopped itself showed PAPER with no reason; the phone's pause showed LIVE
            rec = _jread(P["arm"], {}) or {}
            cst = _jread(KC.paths(P["dir"] if P["dir"] != STATE_DIR else None)["clock_state"], {}) or {}
            if state == "live" and _f(cst.get("paused_until"), 0.0) > now:
                state = c["st"] = "paused"
            if state == "off" and (rec.get("stopped") or os.path.exists(P["kill"])):
                c["st"] = "stopped"
                c["why"] = re.sub(r"[^A-Za-z0-9 $+.,:()%-]", "", str(rec.get("stopped") or "the kill switch is on").replace(": type the phrase again", ""))[:40]
            elif state == "off":
                c["st"] = "paper"           # not armed, but the K8 paper loop runs / has a ledger: the phone shows it (was dropped as 'off')
    except Exception:  # noqa: BLE001
        pass
    while len(json.dumps(c, separators=(",", ":"))) > CARD_MAX and c.get("why"):
        c["why"] = c["why"][:-5]
    return c


def write_card(P, ex=None):
    try:
        _jwrite(P["card"], card(P, ex, now=ex.clock() if ex else None))
    except Exception:  # noqa: BLE001
        pass


def read_card(now=None, state_dir=None):
    """The <=200-byte public card for the PC's ntfy EXT post (key kalshi_live; the Kalshi page reads it). Never raises."""
    try:
        P = paths(state_dir)
        now = time.time() if now is None else now
        k = card(P, now=now) if not loop_alive(P, now) else {}   # day-kalshi QA 2026-11-21: no maker loop (retired) + K8 present = K8's own state + its own loop
        if k.get("k8"):
            if k.get("st") in ("live", "paused") and not k["k8"].get("lp"):
                k["st"] = "idle"                    # armed, but the K8 loop is not running on the PC right now
            return k
        c = _jread(P["card"], None)
        if isinstance(c, dict) and c.get("kind") == "kalshi_live_pub" and now - (os.path.getmtime(P["card"])) < 2 * 86400:
            live, _ = arm_state(P=P)
            if c.get("st") in ("live", "paused") and not live:
                c = card(P, now=now)
            if c.get("st") in ("live", "paused") and not loop_alive(P, now):
                c = dict(c, st="idle")              # armed, but no loop on the PC right now (a PC restart)
            try:                                    # the K8 block is always fresh (the maker loop that writes card.json is idle)
                from engine import kalshi_clock as KC
                k8 = KC.card_k8(P["dir"] if P["dir"] != STATE_DIR else None, now=now)
                if k8:
                    c = dict(c, k8=k8, st="paper" if c.get("st") == "off" else c.get("st"))
            except Exception:  # noqa: BLE001
                pass
            return c
        c = card(P, now=now)                        # no card file (the maker loop never ran): the K8 clock card, or {st: off}
        return c if c.get("st") != "off" else {"kind": "kalshi_live_pub", "v": 1, "st": "off", "u": iso(now)}
    except Exception:  # noqa: BLE001
        return None


def loop_alive(P, now=None) -> bool:
    now = time.time() if now is None else now
    st = _jread(P["state"], {}) or {}
    return now - float(st.get("t") or 0) < HEARTBEAT_STALE_S


def command(cmd, src="pc", state_dir=None, now=None, **extra) -> str:
    """Queue a command for the loop (pause / resume / flatten / kill). Never arms."""
    assert cmd in ("pause", "resume", "flatten", "kill")
    P = paths(state_dir)
    now = time.time() if now is None else now
    c = _jread(P["control"], {}) or {}
    cid = f"{src}-{int(now)}-{secrets.token_hex(3)}"
    rows = [x for x in (c.get("cmds") or []) if isinstance(x, dict)][-19:] + [dict({"id": cid, "cmd": cmd, "t": int(now), "src": src}, **extra)]
    _jwrite(P["control"], {"cmds": rows})
    return cid


def phone_press(action, now=None, state_dir=None, env=None) -> str:
    """engine/phone_safety.run calls this after every ZEUS Safety press. Kalshi OFF and idle = '' (nothing written). It never
    arms: pause / resume / flatten / kill only; a dead loop + flatten / kill = OFF at once + a cancel in a background thread."""
    try:
        P = paths(state_dir)
        now = time.time() if now is None else now
        live, _ = arm_state(P=P, env=env)
        alive = loop_alive(P, now)
        if not live and not alive:
            return ""
        if action == "pause":
            command("pause", "phone", state_dir, now, until=next_4pm(now))
            return "Kalshi: paused (quotes cancelled) until 4 PM ET"
        if action in ("resume", "resume_entries"):
            command("resume", "phone", state_dir, now)
            return "Kalshi: new orders allowed again"
        if action in ("flatten", "kill"):
            command(action, "phone", state_dir, now, flatten=True)
            disarm(P, f"{action.upper()} pressed on the phone", now)
            if action == "kill":
                with open(P["kill"], "w", encoding="utf-8") as fh:
                    fh.write(f"{int(now)} phone\n")
            if not alive:
                threading.Thread(target=_direct_stop, args=(f"{action.upper()} pressed on the phone", True, action == "kill", state_dir, env),
                                 daemon=True).start()
            return f"Kalshi: {action} sent, OFF (orders cancelled, positions sold at the best price)"
        return ""
    except Exception:  # noqa: BLE001
        return ""


def phone_view(state_dir=None, now=None) -> str | None:
    try:
        c = read_card(now, state_dir) or {}
        s = c.get("st")
        if s == "live":
            return f"LIVE, today {money(c.get('net', 0), True)}, {c.get('o', 0)} orders resting"
        if s == "paused":
            return "PAUSED (no new orders)"
        if s == "idle":
            return "ARMED, but not running on the PC right now"
        if s == "stopped":
            return "OFF after a stop" + (f": {c['why']}" if c.get("why") else "")
        return None
    except Exception:  # noqa: BLE001
        return None


def _direct_stop(why, flatten, kill, state_dir=None, env=None, api=None, say=None):
    """A stop without the loop (it is not running): needs the key. Never raises."""
    try:
        api = api or api_from_key(env)
        ex = Executor(api, state_dir=state_dir, env=env, say=say)
        ex.stop(why, scope="all", flatten=flatten, kill=kill)
        save_state(ex.P, ex.st)
        write_card(ex.P, ex)
        return True
    except Exception as e:  # noqa: BLE001
        try:
            log(paths(state_dir), {"t": int(time.time()), "ev": "direct_stop_failed", "why": redact(e)})
        except Exception:  # noqa: BLE001
            pass
        return False


def _lock(path):
    """An OS lock held for the loop's life (released by the OS when the process ends). None = someone else holds it."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = open(path, "a+")
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close()
        return None


def run_loop(state_dir=None, env=None, api=None, max_cycles=None, sleep=time.sleep, clock=time.time, poster=None, alert_cfg=None,
             plan_path=None, cand_dir=None, say=print) -> str:
    P = paths(state_dir)
    fh = _lock(P["lock"])
    if fh is None:
        return "already running"
    try:
        live, why = arm_state(P=P, env=env)
        if not live:
            return "not started: " + why
        if api is None:
            try:
                api = api_from_key(env)
            except KalshiError as e:
                return "not started: " + str(e)
        ex = Executor(api, state_dir=state_dir, plan_path=plan_path, cand_dir=cand_dir, env=env, clock=clock, poster=poster,
                      alert_cfg=alert_cfg, say=say)
        n = 0
        while not ex.done:
            ex.cycle()
            n += 1
            if ex.done or (max_cycles is not None and n >= max_cycles):
                break
            sleep(LOOP_S)
        return "stopped: " + str(ex.stop_why) if ex.stop_why else "ended"
    finally:
        try:
            fh.close()
        except Exception:  # noqa: BLE001
            pass


def spawn(state_dir=None) -> int:
    """The detached, low-priority loop with no window (it outlives KALSHI_LIVE.bat and the 15-minute task)."""
    import subprocess
    P = paths(state_dir)
    os.makedirs(P["dir"], exist_ok=True)
    out = open(P["out"], "a", encoding="utf-8")
    cmd = [sys.executable, "-X", "utf8", "-m", "engine.kalshi_live", "--loop"] + (["--state-dir", state_dir] if state_dir else [])
    kw = {"cwd": ROOT, "stdout": out, "stderr": out, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        base = 0x00004000 | 0x08000000 | 0x00000200          # BELOW_NORMAL | CREATE_NO_WINDOW | NEW_PROCESS_GROUP
        try:
            pid = subprocess.Popen(cmd, creationflags=base | 0x01000000, **kw).pid   # + BREAKAWAY_FROM_JOB
        except OSError:
            pid = subprocess.Popen(cmd, creationflags=base, **kw).pid
    else:
        kw["start_new_session"] = True
        pid = subprocess.Popen(cmd, **kw).pid
    _jwrite(P["run"], {"pid": pid, "t": int(time.time())})
    return pid


def maybe_run(say=print, env=None, now=None, state_dir=None, spawn_fn=None, plan_path=None, cand_dir=None):
    """The PC 15-minute report hook (lead wires it in tools/pc_report.py): restarts the loop ONLY while armed (after a PC restart).
    OFF / not armed / running = nothing. Never raises; returns the new pid or None."""
    try:
        P = paths(state_dir)
        now = time.time() if now is None else now
        try:
            from engine import kalshi_clock
            kalshi_clock.maybe_run(say=say, env=env, now=now, state_dir=state_dir, spawn_fn=spawn_fn)
        except Exception:  # noqa: BLE001
            pass
        live, why = arm_state(P=P, env=env)
        if not live or not load_all(plan_path, cand_dir, state_dir)["maker_runnable"]:
            return None
        if loop_alive(P, now):
            return None
        run = _jread(P["run"], {}) or {}
        if now - float(run.get("t") or 0) < 180:
            return None
        pid = (spawn_fn or spawn)(state_dir)
        say(f"  [..] Kalshi LIVE: loop restarted (pid {pid})")
        return pid
    except Exception:  # noqa: BLE001
        return None


# ================================================================================================ dry run, status, CLI
def dry_run(api=None, plan_path=None, cand_dir=None, now=None, say=print) -> dict:
    """What it would place right now from PUBLIC prices: no key, no POST, no DELETE, nothing saved."""
    api = api or Api(base=os.environ.get("KALSHI_API_BASE") or API_BASE)
    now = time.time() if now is None else now
    ex = Executor(api, plan_path=plan_path, cand_dir=cand_dir, dry=True, clock=lambda: now)
    A = ex.A
    for p in A["problems"]:
        say(f"  [FIX] plan: {p}")
    for s in A["skipped"]:
        say(f"  [..] candidate not traded: {s}")
    if not (A["plan"] or A["cands"]):
        say("  [..] No plan yet (research/lab/kalshi_live_plan.json): nothing to run.")
        return {"orders": [], "blocked": [], "notes": {}}
    want = ex.choose(now, say=say)
    mk, bk = ex.market_data(want, now)
    ex.v = ex.view(now, A["caps"]["capital_cap_usd"], {}, [], mk, bk, True, "")
    orders, notes = ex.desired(now, mk, bk)
    placed, blocked = [], []
    for o in orders:
        o2 = ex.fit(o) if o["kind"] == "quote" else o
        if not o2:
            blocked.append((o, "CAP", "no room left under the caps"))
            continue
        ok, code, words = check_order(o2, ex.v)
        if ok:
            placed.append(o2)
            ex.v["resting"].append({"id": f"dry{len(placed)}", "coid": COID, "ticker": o2["ticker"], "book": o2["book"],
                                    "price": o2["price"], "remaining": float(o2["count"])})
            ex.v["open_orders"] += 1
        else:
            blocked.append((o2, code, words))
    say(f"  DRY RUN {et_text(now)} - public prices, no key, nothing sent.")
    for o in placed:
        q = o["kind"] == "quote"
        side = ("YES bid" if q else "buy YES") if o["book"] == "bid" else ("NO bid " if q else "buy NO ")
        px = o["price"] if o["book"] == "bid" else 1 - o["price"]
        say(f"  would {'rest' if q else 'take'}: {o['ticker'][:34]:<34} {side} {o['count']:>3} at {px * 100:4.0f}c = {money(order_cost(o))}")
    for o, code, words in blocked:
        say(f"  blocked: {o['ticker'][:34]:<34} {o['book']} - {words}")
    for t, w in sorted(notes.items()):
        say(f"  no quote: {t[:34]:<34} {w}")
    say(f"  Total if all go in: {len(placed)} orders, {money(used_total(ex.v))} of the {money(A['caps']['capital_cap_usd'])} cap.")
    return {"orders": placed, "blocked": blocked, "notes": notes, "api_writes": api.writes}


def describe(A) -> list:
    caps, out = A["caps"], []
    if A.get("clock_ok"):
        from engine import kalshi_clock
        out += kalshi_clock.describe(A["clock"])
    for p in A.get("clock_problems") or []:
        out.append(f"[FIX] clock settings: {p}")
    if A["plan"]:
        p = A["plan"]
        out.append(f"Plan: {p['strategy'].replace('_', ' ')} (status: {p['status'] or '?'}{', ' + p['date'] if p['date'] else ''})")
        for m in p["markets"]:
            pz = ", ".join(f"{r['hours']:g} h before close" if r["type"] == "before_close" else
                           f"{r['minutes']:g} min after a {r['cents']:g}c move" if r["type"] == "after_move" else
                           f"spread over {r['cents']:g}c" if r["type"] == "wide_spread" else f"{r['minutes']:g} min before the reward ends"
                           for r in m["pause"]) or "the defaults"
            out.append(f"  {m['series']}: up to {m['max_markets']} market{'s' if m['max_markets'] != 1 else ''}, {m['size']} contracts a side, "
                       f"{m['offset_cents']}c behind the reward price; pauses: {pz}")
        for u in p["unproven"][:3]:
            out.append(f"  Not proven yet: {u}")
    for c in A["cands"]:
        out.append(f"Taker rule {c['name']}: {', '.join(r['series'] for r in c['rules'])}, {money(c['usd'])} a bet, "
                   f"price {c['band'][0] * 100:.0f}-{c['band'][1] * 100:.0f}c (status {c['status']})")
    if A.get("maker_runnable"):
        out.append(f"Limits (checked before every order): {money(caps['capital_cap_usd'])} total, {money(caps['per_market_cap_usd'])} a market, "
                   f"stop at -{money(caps['daily_loss_stop_usd'])} a day, at most {caps['max_open_orders']} orders resting.")
    return out


def status_lines(state_dir=None, env=None, now=None) -> list:
    P = paths(state_dir)
    now = time.time() if now is None else now
    A = load_all()
    live, why = arm_state(P=P, sha=A["sha"], env=env)
    kf = key_files(env)
    key = "found (outside the bot folder)" if os.path.isfile(kf["key_file"]) and kf["key_id"] and not inside_repo(kf["key_file"]) \
        else "NOT set up yet: double-click KALSHI_KEY_SETUP.bat"
    c = card(P, now=now)
    lines = [f"KALSHI LIVE: {'LIVE' if live else 'OFF'} - {why}", f"Key: {key}",
             f"Loop: {'running' if loop_alive(P, now) else 'not running'}"]
    if c.get("st") in ("live", "paused", "stopped"):
        lines.append(f"Today: {money(c.get('net', 0), True)}, {c.get('f', 0)} fills, {c.get('o', 0)} orders resting")
    lines += describe(A) if (A["plan"] or A["cands"]) else ["No plan yet (research/lab/kalshi_live_plan.json)."]
    lines += [f"[FIX] plan: {p}" for p in A["problems"][:4]]
    if not live:
        lines.append(f"To go live: double-click KALSHI_LIVE.bat and type  {PHRASE}")
    return lines


def go(state_dir=None, env=None, input_fn=input, say=print, spawn_fn=None, api=None, dry_api=None, plan_path=None, cand_dir=None,
       poster=None, alert_cfg=None, now=None) -> int:
    """KALSHI_LIVE.bat: plan + key + dry run, then YOU type the phrase, then the loop starts in the background."""
    say("\n KALSHI LIVE: real money, small. Nothing is sent until you type the phrase.\n")
    if off_by_env(env):
        say(" [FIX] LE_KALSHI_LIVE=0 switches Kalshi off on this PC. Nothing armed.")
        return 1
    P = paths(state_dir)
    A = load_all(plan_path, cand_dir, state_dir)
    if arm_state(P=P, sha=A["sha"], env=env)[0] and (loop_alive(P, now) or not A["maker_runnable"]):
        say(" [OK] Kalshi is already LIVE and running: nothing to do. Stop: KALSHI_STOP.bat or the phone's ZEUS Safety page.")
        return 0
    say(" 1/4 What it trades")
    for ln in (describe(A) if (A["plan"] or A["cands"]) else ["No plan yet (research/lab/kalshi_live_plan.json)."]):
        say("     " + ln)
    if not A["runnable"]:
        for p in (A["problems"] + A["clock_problems"])[:4]:
            say(f" [FIX] plan: {p}")
        say(" [FIX] The plan cannot go live as it is: ask Claude to fix it. Nothing armed.")
        return 1
    clock_spawn = None
    try:
        from engine import kalshi_clock
        clock_spawn = kalshi_clock.maybe_run(say=lambda *_: None, env=env, now=now, state_dir=state_dir,
                                             spawn_fn=(spawn_fn and (lambda sd: spawn_fn(sd))))
        for ln in kalshi_clock.report_lines(state_dir):
            say("     " + ln)
    except Exception:  # noqa: BLE001
        pass
    say(" 2/4 Your Kalshi key")
    try:
        api = api or api_from_key(env)
        b = api.get("/portfolio/balance")
        bal = _f(b.get("balance_dollars"), (_f(b.get("balance"), 0.0) or 0.0) / 100.0)
        say(f"     [OK] The key works. Cash on Kalshi: {money(bal)}.")
    except KalshiError as e:
        say(f" [FIX] {key_fix(e)} Nothing armed.")
        return 1
    if bal < 1:
        say(" [FIX] There is no cash on Kalshi: add money in the Kalshi app first. Nothing armed.")
        return 1
    say(" 3/4 What it would place right now (public prices)")
    try:
        dry_run(api=dry_api, plan_path=plan_path, cand_dir=cand_dir, now=now, say=lambda s: say("   " + s))
    except Exception as e:  # noqa: BLE001
        say(f"     (the preview did not run: {e.__class__.__name__})")
    say(f"\n 4/4 To start real money, type exactly:  {PHRASE}")
    try:
        typed = input_fn("     > ")
    except (EOFError, KeyboardInterrupt):
        typed = ""
    ok, msg = arm(typed, state_dir=state_dir, plan_path=plan_path, cand_dir=cand_dir, env=env, now=now, expect_sha=A["sha"])
    if not ok:
        say(f" Stopped: {msg}. Nothing is armed.")
        return 1
    ex = Executor(api, state_dir=state_dir, plan_path=plan_path, cand_dir=cand_dir, env=env, poster=poster, alert_cfg=alert_cfg,
                  clock=(lambda: now) if now is not None else time.time)
    ex.push("armed", f"Kalshi LIVE armed | cap {money(A['caps']['capital_cap_usd'])} | stop -{money(A['caps']['daily_loss_stop_usd'])}/day",
            "Pause or flatten: the phone's ZEUS Safety page. Stop: KALSHI_STOP.bat on the PC. Fills come batched, then one day summary.",
            priority="default", tags="rocket")
    save_state(P, ex.st)
    pid = (spawn_fn or spawn)(state_dir) if A["maker_runnable"] else clock_spawn or "already running"
    say(f"\n [OK] Kalshi LIVE is on (loop {pid}). Pushes: each bet, each result, the day's summary, any stop.")
    say("      Pause / flatten from the phone: the ZEUS Safety page. Stop here: double-click KALSHI_STOP.bat.")
    return 0


def key_fix(e) -> str:
    s = str(e)
    if getattr(e, "status", None) == 401 or "401" in s:
        return "Kalshi refused the key: make a new API key on kalshi.com, then double-click KALSHI_KEY_SETUP.bat again."
    if getattr(e, "code", "") in ("no_key", "bad_key", "key_in_repo", "no_crypto"):
        return s[:200]
    return "Kalshi could not be reached (" + s[:120] + "): check the internet, then try again."


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Kalshi LIVE executor (OFF by default; the owner arms it with the typed phrase)")
    g = ap.add_mutually_exclusive_group()
    for f in ("--status", "--dry-run", "--check-key", "--go", "--loop", "--start", "--stop", "--pause", "--resume", "--flatten",
              "--clock-loop", "--clock-report"):
        g.add_argument(f, action="store_true")
    g.add_argument("--arm", action="store_true", help="arm only (the owner types the phrase; --phrase for a script he runs)")
    ap.add_argument("--phrase", default=None)
    ap.add_argument("--state-dir", default=None)
    a = ap.parse_args(argv)
    sd = a.state_dir
    P = paths(sd)
    if a.dry_run:
        dry_run()
        return 0
    if a.clock_loop or a.clock_report:
        from engine import kalshi_clock
        if a.clock_report:
            ccfg = kalshi_clock.load_config(state_dir=sd)[0]
            k = kalshi_clock.kill_distances(sd, ccfg)
            stops = [f"How far each stop is ({k['ledger']}): today {money(-k['day']['used'])} of {money(-k['day']['stop'])}, this week "
                     f"{money(-k['week']['used'])} of {money(-k['week']['stop'])}, from the peak {money(-k['drawdown']['used'])} of "
                     f"{money(-k['drawdown']['stop'])}; last 10: " + ("".join("W" if r["result"] == "won" else "L" for r in k["last10"]) or "none")]
            for ln in kalshi_clock.describe(ccfg) + kalshi_clock.report_lines(sd) + stops + kalshi_clock.files_lines(sd):
                print("  " + ln)
            return 0
        print(f"{iso(time.time())} kalshi clock loop: {kalshi_clock.run(state_dir=sd)}", flush=True)
        return 0
    if a.check_key:
        try:
            b = api_from_key().get("/portfolio/balance")
            print(f"  [OK] Kalshi key works. Cash on Kalshi: {money(_f(b.get('balance_dollars'), (_f(b.get('balance'), 0.0) or 0.0) / 100.0))}.")
            return 0
        except KalshiError as e:
            print(f"  [FIX] {key_fix(e)}")
            return 1
    if a.go:
        return go(state_dir=sd)
    if a.arm:
        phrase = a.phrase if a.phrase is not None else input(f"Type exactly  {PHRASE}  and press Enter: ")
        ok, msg = arm(phrase, state_dir=sd)
        print(f"  [{'OK' if ok else 'FIX'}] Kalshi: {msg}")
        return 0 if ok else 1
    if a.loop:
        print(f"{iso(time.time())} kalshi_live loop: {run_loop(state_dir=sd)}", flush=True)
        return 0
    if a.start:
        live, why = arm_state(P=P)
        if not live:
            print(f"  [FIX] Kalshi not started: {why}")
            return 1
        print(f"  [OK] Kalshi loop {'already running' if loop_alive(P) else 'started (pid ' + str(spawn(sd)) + ')'}")
        return 0
    if (a.stop or a.flatten or a.pause or a.resume) and _jread(P["arm"], None) is None and not loop_alive(P):
        print("  [OK] Kalshi is OFF already (it was never switched on on this PC): nothing to stop or pause.")
        return 0
    if a.stop or a.flatten:
        what = "flatten" if a.flatten else "kill"
        command(what, "pc", sd, flatten=a.flatten)
        if a.stop:
            with open(P["kill"], "w", encoding="utf-8") as fh:
                fh.write(f"{int(time.time())} KALSHI_STOP\n")
        disarm(P, "FLATTEN at the PC" if a.flatten else "KALSHI_STOP at the PC")
        if loop_alive(P):
            print("  [OK] Kalshi: the loop is cancelling every order and switching OFF (one phone push confirms).")
            return 0
        ok = _direct_stop("FLATTEN at the PC" if a.flatten else "KALSHI_STOP at the PC", a.flatten, a.stop, sd)
        print("  [OK] Kalshi: every resting order cancelled, OFF." if ok else
              "  [OK] Kalshi is OFF. (No key or no answer: check the Kalshi app for resting orders; each expires within 20 minutes.)")
        return 0
    if a.pause or a.resume:
        command("pause" if a.pause else "resume", "pc", sd, until=next_4pm(time.time()) if a.pause else None)
        print(f"  [OK] Kalshi: {'paused until 4 PM ET (quotes cancelled)' if a.pause else 'new orders allowed again'}")
        return 0
    for ln in status_lines(sd):
        print("  " + ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
