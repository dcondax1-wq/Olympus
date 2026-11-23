"""Web Push notifications to the phone: Olympus, the Home Screen app at https://dcondax1-wq.github.io/jarvis/ (2026-11-19).

Owner 2026-11-19: "I want notifications on my phone." The PC owns its key and talks to the phone without any cloud or GitHub step
(the old flow below, a GitHub Actions cloud monitor handing the key to the PC, died with that GitHub account on Nov 8):
  key      the PC makes its VAPID key pair once (own_key, data/push.json, gitignored). The PUBLIC key + the PC's box key
           (data/push_pc_key.json) ride its 15-minute status core post ("wp", app_block): no extra ntfy post.
  phone    Olympus's "Allow notifications" (tools/web_public/jarvis/push-ui.js) subscribes with that key and posts the subscription,
           sealed to the PC's box key, to the free relay topic (tools/web_public/push_relay.json).
  intake   the PC's 5-minute ops task reads the relay (engine/alerts_plus.ops_tick -> intake): the phone joins data/push.json
           "devices" and gets one welcome push; "Send a test" / "Turn off" work the same way.
  send     every real-account entry and exit (pc_notify, at once, "Zlarior 50K: LONG opened" / "... closed +$605"), the 15-minute
           report's alerts (tools/pc_report.py) and tests go to the phone; the private ntfy topic is the backup, used only when no
           phone took the alert (never twice on one phone). jarvis/push-sw.js shows them (one notification per trade: the exit
           replaces the entry) and opens Olympus at the NQ page / the Board.

Payloads: entry_payload / outcome_payload / text_payload (tag per trade, url, key for de-duplication). Sending: pywebpush when
installed, else the built-in RFC 8291 (aes128gcm) + RFC 8292 (VAPID) sender (needs only `cryptography`). Nothing configured or no
`cryptography` = every call is a silent no-op and the ntfy alerts carry on. Never raises into the trading loops.

The old cloud flow (kept for its tests; nothing on the PC uses it now): the relay held the old app's plain subscriptions, the cloud
kept its key in the Actions cache and sealed it to the PC (pc_sync, state.json on the dashboard branch), both sides posted "sent"
markers so a trade was notified once. Manual overrides still work: LE_PUSH_SUBS (+ _2.._5), data/push.json "subs".
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "data", "push.json")            # PC manual override, gitignored
SENT_PATH = os.path.join(ROOT, "data", "push_sent.json")         # PC de-dup keys, gitignored
PC_KEY_PATH = os.path.join(ROOT, "data", "push_pc_key.json")     # the PC's own key (receives the VAPID key), gitignored
# engine/pc_selftest runs the repo's suites ON the owner's PC in sealed child processes (LE_SELFTEST_CHILD=1): there no real
# push goes out, the ntfy relay is never called, and the PC's own push files are never read or written (temp copies)
SEALED = os.environ.get("LE_SELFTEST_CHILD") == "1"
if SEALED:
    import tempfile as _tempfile
    CONFIG_PATH, SENT_PATH, PC_KEY_PATH = (os.path.join(_tempfile.gettempdir(), f"le_selftest_{os.path.basename(_p)}")
                                           for _p in (CONFIG_PATH, SENT_PATH, PC_KEY_PATH))
RELAY_PATH = os.path.join(ROOT, "tools", "web_public", "push_relay.json")
APP_URL = "https://dcondax1-wq.github.io/"
SUBJECT = os.environ.get("LE_PUSH_SUBJECT") or "https://dcondax1-wq.github.io"   # VAPID "sub" claim: a contact URL, host only
TTL_S = 6 * 3600
MAX_SUBS = 10
# push services a subscription may point at (the relay is public: nothing else is ever POSTed to)
PUSH_HOSTS = ("web.push.apple.com", "fcm.googleapis.com", "updates.push.services.mozilla.com", "push.services.mozilla.com",
              "notify.windows.com", "android.googleapis.com")
_lock = threading.Lock()


# ---------------------------------------------------------------------------------------------- base64url helpers
def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_dec(s: str) -> bytes:
    s = str(s).strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def endpoint_id(endpoint: str) -> str:
    """Short, non-reversible id of a subscription (the app compares it with its own to say 'this phone is on')."""
    return hashlib.sha256(str(endpoint).encode()).hexdigest()[:12]


def extra_on() -> bool:
    """Notices other than entry / outcome (PC silent, eval timing, NinjaTrader trouble): app-only unless LE_PUSH_EXTRA=1."""
    return os.environ.get("LE_PUSH_EXTRA", "") == "1"


# ---------------------------------------------------------------------------------------------- keys
def _priv_from_b64(priv_b64: str):
    from cryptography.hazmat.primitives.asymmetric import ec
    raw = b64u_dec(priv_b64)
    if len(raw) != 32:
        raise ValueError("the VAPID private key must be 32 bytes (base64url, 43 characters)")
    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())


def _pub_bytes(pub) -> bytes:
    from cryptography.hazmat.primitives import serialization
    return pub.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def public_from_private(priv_b64: str) -> str:
    """The app's applicationServerKey (base64url of the 65-byte uncompressed point) for a private key."""
    return b64u(_pub_bytes(_priv_from_b64(priv_b64).public_key()))


def generate_keys() -> tuple[str, str]:
    """A new P-256 key pair: (private, public), both base64url."""
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    return b64u(k.private_numbers().private_value.to_bytes(32, "big")), b64u(_pub_bytes(k.public_key()))


def _read_json(path) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def _write_private(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, path)


def ensure_key_file(path: str) -> dict:
    """Cloud: the VAPID key pair kept in the Actions cache, made on the first run when the file is missing or broken.
    Returns {"public", "new"}: never the private key (callers must not print it)."""
    k = _read_json(path)
    try:
        return {"public": public_from_private(k["private"]), "new": False}
    except Exception:
        priv, pub = generate_keys()
        _write_private(path, {"private": priv, "made": int(time.time())})
        return {"public": pub, "new": True}


# ---- ECIES: the cloud hands the VAPID private key to the PC without anyone copying it
def seal(secret: bytes, recipient_pub_b64: str, info: bytes = b"le-push-pc-v1") -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    rp = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b64u_dec(recipient_pub_b64))
    eph = ec.generate_private_key(ec.SECP256R1())
    key = HKDF(hashes.SHA256(), 32, None, info).derive(eph.exchange(ec.ECDH(), rp))
    nonce = os.urandom(12)
    return b64u(_pub_bytes(eph.public_key()) + nonce + AESGCM(key).encrypt(nonce, secret, None))


def unseal(box_b64: str, recipient_priv_b64: str, info: bytes = b"le-push-pc-v1") -> bytes:
    """Open a box sealed to the PC's key: 65-byte ephemeral P-256 point + 12-byte nonce + AES-256-GCM (HKDF-SHA256 over the ECDH
    secret, no salt, `info` = the label of what it carries: the old cloud key hand-off, or a phone's subscription SUB_INFO)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    b = b64u_dec(box_b64)
    eph = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b[:65])
    key = HKDF(hashes.SHA256(), 32, None, info).derive(_priv_from_b64(recipient_priv_b64).exchange(ec.ECDH(), eph))
    return AESGCM(key).decrypt(b[65:77], b[77:], None)


def pc_public_key(path: str | None = None) -> str | None:
    """The PC's own public key for the heartbeat (made once, private part in data/push_pc_key.json). Never raises."""
    path = path or PC_KEY_PATH
    try:
        k = _read_json(path)
        if k.get("private"):
            return public_from_private(k["private"])
        priv, pub = generate_keys()
        _write_private(path, {"private": priv, "made": int(time.time())})
        return pub
    except Exception:
        return None


# ---------------------------------------------------------------------------------------------- subscriptions
def _good_endpoint(ep) -> bool:
    if not (isinstance(ep, str) and ep.startswith("https://")):
        return False
    host = urllib.parse.urlsplit(ep).hostname or ""
    return any(host == h or host.endswith("." + h) for h in PUSH_HOSTS)


def parse_subs(text) -> list:
    """Subscriptions from a secret's text / a list: a JSON list, one object, or several objects one after another.
    Keeps only well-formed ones on a known push service {endpoint, keys: {p256dh, auth}}, de-duplicated by endpoint."""
    if not text:
        return []
    items = []
    if isinstance(text, (list, dict)):
        items = text if isinstance(text, list) else [text]
    else:
        s, dec, i = str(text).strip(), json.JSONDecoder(), 0
        while i < len(s):
            while i < len(s) and s[i] in " \t\r\n,;":
                i += 1
            if i >= len(s):
                break
            try:
                obj, i = dec.raw_decode(s, i)
            except ValueError:
                break
            items += obj if isinstance(obj, list) else [obj]
    out, seen = [], set()
    for x in items:
        if not isinstance(x, dict):
            continue
        ep, keys = x.get("endpoint"), x.get("keys") or {}
        if not (_good_endpoint(ep) and keys.get("p256dh") and keys.get("auth")) or ep in seen:
            continue
        seen.add(ep)
        out.append({"endpoint": ep, "keys": {"p256dh": str(keys["p256dh"]), "auth": str(keys["auth"])}})
    return out


# ---------------------------------------------------------------------------------------------- relay (ntfy.sh)
# sub / unsub: the app's push subscription (v 2 = Olympus, sealed to the PC: engine/push.intake); test: Olympus's "Send a test"
# (sealed); sent: a notice the cloud / PC already pushed; ack: the app's "Got it" on a critical alert; prefs: the app's on / silent /
# off levels; crit: a sender's open critical alerts (engine/alerts_plus.py)
RELAY_KINDS = ("sub", "unsub", "test", "sent", "ack", "prefs", "crit")


class Relay:
    """The free ntfy.sh topic: the app posts {"le": "sub", ...}; the cloud / PC post {"le": "sent", "key"}. ntfy keeps
    messages about 12 h, so the app posts again on each open until the cloud lists the phone. Never raises."""

    def __init__(self, base=None, topic=None, timeout=10.0, http=None):
        cfg = _read_json(RELAY_PATH)
        self.base = (base or os.environ.get("LE_PUSH_RELAY") or cfg.get("ntfy") or "https://ntfy.sh").rstrip("/")
        self.topic = topic or os.environ.get("LE_PUSH_TOPIC") or cfg.get("topic")
        self.timeout = timeout
        self.http = http                     # tests: http(method, url, body) -> text
        self.error = None

    def ok(self) -> bool:
        return bool(self.topic)

    def public(self) -> dict:
        return {"ntfy": self.base, "topic": self.topic}

    def _req(self, method, url, body=None):
        if self.http is not None:
            return self.http(method, url, body)
        if SEALED:
            raise RuntimeError("PC self-test child: the relay is not called")
        req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": "LiquidityEngine/1.0"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.read().decode("utf-8", "replace")

    def read(self, since: str = "all") -> list:
        """Every relay message still on the topic: [{"le": ..., ..., "_t"}] (anything else on the topic is ignored)."""
        if not self.ok():
            return []
        try:
            text = self._req("GET", f"{self.base}/{self.topic}/json?poll=1&since={since}")
        except Exception as e:
            self.error = e.__class__.__name__
            return []
        out = []
        for line in str(text or "").splitlines():
            try:
                m = json.loads(line)
                if m.get("event") not in (None, "message"):
                    continue
                body = json.loads(m.get("message") or "")
                if isinstance(body, dict) and body.get("le") in RELAY_KINDS:
                    body["_t"] = int(m.get("time") or 0)
                    out.append(body)
            except Exception:
                continue
        return out

    def post(self, obj: dict) -> bool:
        if not self.ok():
            return False
        try:
            self._req("POST", f"{self.base}/{self.topic}", json.dumps(obj, separators=(",", ":")).encode())
            return True
        except Exception as e:
            self.error = e.__class__.__name__
            return False

    def sent_keys(self, msgs=None) -> set:
        return {str(m["key"]) for m in (self.read() if msgs is None else msgs) if m.get("le") == "sent" and m.get("key")}


def merge_relay_subs(stored: list, msgs: list, public: str | None, gone=(), now=None) -> list:
    """The cloud's subscription list: stored rows + "sub" messages made with today's key, minus "unsub" / expired ones,
    newest MAX_SUBS. Rows: {"sub", "id", "key", "t"}."""
    rows = {r["id"]: r for r in stored or [] if r.get("id") and r.get("sub")}
    for m in sorted(msgs or [], key=lambda x: x.get("_t", 0)):
        if m.get("le") == "sub":
            subs = parse_subs(m.get("sub"))
            if not subs:
                continue
            sid = endpoint_id(subs[0]["endpoint"])
            rows[sid] = {"sub": subs[0], "id": sid, "key": m.get("key"), "t": int(m.get("_t") or now or time.time())}
        elif m.get("le") == "unsub" and m.get("id") in rows and int(m.get("_t") or 0) >= rows[m["id"]].get("t", 0):
            rows.pop(m["id"], None)
    gone = set(gone or [])
    keep = [r for r in rows.values() if r["id"] not in gone and (not public or not r.get("key") or r["key"] == public)]
    return sorted(keep, key=lambda r: r["t"])[-MAX_SUBS:]


# ---------------------------------------------------------------------------------------------- config
def config(env=None, path=None, subs_extra=None, private=None) -> dict:
    """{"private", "public", "subs", "source", "error"}; private None = not configured.
    Private key: LE_VAPID_PRIVATE (secret) > LE_VAPID_KEY_FILE (cloud cache) > `private` (the PC's synced key) > data/push.json."""
    env = os.environ if env is None else env
    f = _read_json(path or CONFIG_PATH)
    kf = _read_json(env.get("LE_VAPID_KEY_FILE")) if env.get("LE_VAPID_KEY_FILE") else {}
    cands = [("secret", (env.get("LE_VAPID_PRIVATE") or "").strip()), ("cache", (kf.get("private") or "").strip()),
             ("pc-sync", (private or "").strip()), ("file", (f.get("vapid_private") or "").strip())]
    src, priv = next(((s, p) for s, p in cands if p), (None, None))
    subs = []
    for t in [env.get("LE_PUSH_SUBS")] + [env.get(f"LE_PUSH_SUBS_{i}") for i in range(2, 6)]:
        subs += parse_subs(t)
    subs = parse_subs(subs + parse_subs(f.get("subs")) + parse_subs(subs_extra or []))
    pub, err = None, None
    if priv:
        try:
            pub = public_from_private(priv)
        except Exception as e:
            err, priv, src = f"VAPID private key unusable ({e.__class__.__name__})", None, None
    return {"private": priv, "public": pub, "subs": subs, "source": src, "error": err}


def enabled(cfg=None) -> bool:
    c = cfg or config()
    return bool(c["private"] and c["subs"])


def status(cfg=None, **extra) -> dict:
    """Public view for the dashboards: never the private key or an endpoint, only short endpoint ids."""
    c = cfg or config()
    return {"configured": bool(c["private"]), "vapid_public": c["public"], "devices": len(c["subs"]),
            "device_ids": [endpoint_id(s["endpoint"]) for s in c["subs"]], "source": c["source"], "error": c["error"],
            "sender": sender_name(), **extra}


# ---------------------------------------------------------------------------------------------- payloads
MINUS = "−"


def money(x) -> str:
    """+$1,812 / −$366 / $0 (whole dollars, a real minus sign)."""
    v = round(float(x or 0))
    return "$0" if v == 0 else f"{'+' if v > 0 else MINUS}${abs(v):,.0f}"


def account_label(lm: dict | None = None, kind: str = "live") -> str:
    """live_model.json "account": {"name": "MFFU 50K", "paper": "Paper"} (both optional)."""
    a = (lm or {}).get("account") or {}
    return str(a.get("paper") or "Paper") if kind == "paper" else str(a.get("name") or "MFFU 50K")


def trade_tag(entry_t) -> str:
    """One notification per trade: the outcome replaces the entry (the same tag from the cloud and the PC)."""
    return f"le-trade-{int(entry_t or 0)}"


def _hm(t) -> str:
    try:
        import datetime as dt
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(int(t), ZoneInfo("America/New_York")).strftime("%H:%M")
    except Exception:
        return ""


def entry_payload(account: str, side: str, qty, entry_t, src: str = "", contract: str = "MNQ", **detail) -> dict:
    """ENTRY: title "LONG · MFFU 50K", body "Entered 4 MNQ". detail (entry, stop, target, risk_usd, setup...) stays in the
    app's Activity page; it is never sent."""
    side = str(side or "").upper()
    return {"kind": "fill", "key": f"fill:{int(entry_t or 0)}", "t": int(entry_t or time.time()), "src": src, "account": account,
            "title": f"{side} · {account}", "body": f"Entered {int(qty or 0)} {contract}", "tag": trade_tag(entry_t),
            "url": f"#/activity/fill:{int(entry_t or 0)}", "side": side, "qty": qty, **detail}


def outcome_payload(account: str, side: str, exit_reason: str, usd, entry_t, exit_t=None, src: str = "", **detail) -> dict:
    """OUTCOME: title "LONG · MFFU 50K", body "+$1,812" / "−$366" / "$0 breakeven" / "+$212 closed 15:55"."""
    side, reason = str(side or "").upper(), str(exit_reason or "").upper()
    body = money(usd)
    if reason == "BE":
        body += " breakeven"
    elif reason in ("TIME", "EOD", "TIME SAFETY", "KILL"):
        body += f" closed {_hm(exit_t)}" if exit_t else " closed"
    return {"kind": "outcome", "key": f"out:{int(entry_t or 0)}", "t": int(exit_t or time.time()), "src": src, "account": account,
            "title": f"{side} · {account}", "body": body, "tag": trade_tag(entry_t), "url": f"#/activity/out:{int(entry_t or 0)}",
            "side": side, "exit": reason, "usd": round(float(usd or 0), 2), **detail}


def text_payload(src: str, kind: str, title: str, body: str, key: str, t=None, url: str = "#/activity") -> dict:
    """Other notices (PC silent, eval timing, NinjaTrader trouble, test): app-only unless LE_PUSH_EXTRA=1 (a test: always)."""
    return {"kind": kind, "src": src, "key": key, "t": int(t or time.time()), "title": str(title)[:120], "body": str(body)[:600],
            "tag": f"le-{kind}", "url": url}


# ---------------------------------------------------------------------------------------------- PC offline (the Surface)
# The cloud monitor's loud "Surface offline" push (owner 2026-10-20: the Surface slept at 20:46 ET and the bot could not trade):
# heartbeat older than 30 min inside 01:30-16:00 ET on a weekday (the cloud's ~01:32 ET run is the night check) -> ONE push per
# outage (key = the last check-in time, so a later run never repeats it) and one "back online" push when it reports again.
PC_OFFLINE_AFTER_S = 30 * 60
PC_OFFLINE_WINDOW = (90, 960)          # 01:30-16:00 ET, minutes after midnight, weekdays


def _et_dt(t):
    import datetime as _dt
    from zoneinfo import ZoneInfo
    return _dt.datetime.fromtimestamp(int(t), ZoneInfo("America/New_York"))


def pc_offline_window(now) -> bool:
    """True on a weekday 01:30-16:00 ET (LIT enters 02:00-15:30 ET; the 01:30 run checks the PC before the session)."""
    e = _et_dt(now)
    mod = e.hour * 60 + e.minute
    if not (e.weekday() < 5 and PC_OFFLINE_WINDOW[0] <= mod <= PC_OFFLINE_WINDOW[1]):
        return False
    try:                                   # 2026-10-29: not on a CME full closure (Christmas, New Year's Day: no session)
        from .cme_calendar import full_closure
        return not full_closure(e.date())
    except Exception:
        return True


def pc_since_text(t, now) -> str:
    """'20:46' for today (ET), 'Mon 20:46' for an earlier day."""
    e, n = _et_dt(t), _et_dt(now)
    return e.strftime("%H:%M") if e.date() == n.date() else e.strftime("%a %H:%M")


def pc_checkin_line(hb: dict | None, now) -> dict:
    """The README / app line for the PC's last heartbeat: {"t", "age_s", "offline", "in_window", "text"}."""
    hb = hb or {}
    now = int(now)
    t = int(hb.get("t") or 0) if hb.get("present") else 0
    if not t:
        return {"t": None, "age_s": None, "offline": True, "in_window": pc_offline_window(now),
                "text": "no check-in from the Surface yet (no heartbeat)"}
    age = max(0, now - t)
    off = age > PC_OFFLINE_AFTER_S
    win = pc_offline_window(now)
    a = f"{age // 60} min" if age < 5400 else f"{age / 3600:.1f} h"
    txt = f"last check-in {pc_since_text(t, now)} ET ({a} ago)"
    if off and win:
        txt = f"**OFFLINE since {pc_since_text(t, now)} ET** ({a}): the bot can't trade"
    elif off:
        txt += ", offline (outside trading hours)"
    return {"t": t, "age_s": age, "offline": off, "in_window": win, "text": txt}


def pc_offline_payload(since_t, now, host: str | None = None, position: bool = False) -> dict:
    s = pc_since_text(since_t, now)
    body = (f"Surface offline since {s} ET — the bot can't trade. Check it's awake and NinjaTrader is connected."
            + (" A POSITION WAS OPEN: check NinjaTrader / MFFU now." if position else ""))
    p = text_payload("Cloud", "pc", f"Surface offline since {s} ET", body, key=f"pc_offline:{int(since_t)}", t=now, url="#/today")
    p.update(tag="le-pc-offline", require=True)
    return p


def pc_back_payload(since_t, back_t, now) -> dict:
    s, b = pc_since_text(since_t, now), pc_since_text(back_t, now)
    p = text_payload("Cloud", "pc", "Surface back online",
                     f"Surface back online at {b} ET (offline since {s} ET). The bot can trade again; check the Home page is green.",
                     key=f"pc_back:{int(since_t)}", t=now, url="#/today")
    p["tag"] = "le-pc-offline"                 # replaces the offline notice on the phone
    return p


def pc_outage(prev: dict | None, hb: dict | None, now) -> tuple[dict, list]:
    """One step of the cloud's outage tracker. prev = state.json "pc_outage" ({"since", "alerted_at", "back_at"} or {}),
    hb = engine/heartbeat.read(). Returns (new state, notices to push). An outage starts when the last check-in is older than
    30 min; its key is that check-in time, so it is pushed once (only inside 01:30-16:00 ET on a weekday, the first run there
    when it started earlier) and, if it was pushed, closed with one "back online" notice. No heartbeat branch at all (the
    fetch failed) changes nothing."""
    now = int(now)
    prev = dict(prev or {})
    hb = hb or {}
    if not hb.get("present") or not hb.get("t"):
        return prev, []
    t = int(hb["t"])
    age = now - t
    out = []
    if age > PC_OFFLINE_AFTER_S:
        cur = prev if prev.get("since") == t and not prev.get("back_at") else {"since": t}
        if not cur.get("alerted_at") and pc_offline_window(now):
            out.append(pc_offline_payload(t, now, hb.get("host"), bool(hb.get("position"))))
            cur["alerted_at"] = now
        return cur, out
    if prev.get("since") and not prev.get("back_at"):
        if prev.get("alerted_at"):
            out.append(pc_back_payload(prev["since"], t, now))
        return {"since": prev["since"], "alerted_at": prev.get("alerted_at"), "back_at": t}, out
    return prev, out


def wire(payload: dict) -> bytes:
    """What goes to the phone (well under the 4 KB push limit): title, body, tag, url, kind, key, t (+ require: the
    notification stays on screen until tapped, the Surface-offline alert; + image: a recap card / brief PNG on the app's
    site, shown by phones that support notification images, e.g. Android Chrome; iPhone shows the text and the tap opens it)."""
    keep = {k: payload.get(k) for k in ("title", "body", "tag", "url", "kind", "key", "t")}
    if payload.get("require"):
        keep["require"] = True
    if payload.get("silent"):
        keep["silent"] = True         # level "silent" (engine/alerts_plus.py): shown without sound
    if payload.get("ack"):
        keep["ack"] = str(payload["ack"])[:80]    # a critical alert: the app's "Got it" posts this id to the relay
    img = payload.get("image")
    if isinstance(img, str) and img.startswith(APP_URL) and len(img) < 300:
        keep["image"] = img           # recap card / brief PNG on the app's own site (tools/recap.py); phones that show images do
    return json.dumps(keep, separators=(",", ":"), ensure_ascii=False).encode()


# ---------------------------------------------------------------------------------------------- built-in sender
def _hmac(key, data):
    import hmac
    return hmac.new(key, data, hashlib.sha256).digest()


def encrypt(plaintext: bytes, p256dh: str, auth: str, salt: bytes | None = None, as_key=None) -> bytes:
    """RFC 8291 message encryption, aes128gcm content coding (RFC 8188), one record."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    ua_pub = b64u_dec(p256dh)
    auth_secret = b64u_dec(auth)
    as_key = as_key or ec.generate_private_key(ec.SECP256R1())
    as_pub = _pub_bytes(as_key.public_key())
    shared = as_key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub))
    ikm = _hmac(_hmac(auth_secret, shared), b"WebPush: info\x00" + ua_pub + as_pub + b"\x01")
    salt = salt or os.urandom(16)
    prk = _hmac(salt, ikm)
    cek = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]
    ct = AESGCM(cek).encrypt(nonce, plaintext + b"\x02", None)
    return salt + struct.pack("!IB", 4096, len(as_pub)) + as_pub + ct


def vapid_header(endpoint: str, priv_b64: str, pub_b64: str | None = None, subject: str = SUBJECT, now=None) -> str:
    """RFC 8292: 'vapid t=<ES256 JWT>, k=<public key>'."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    u = urllib.parse.urlsplit(endpoint)
    claims = {"aud": f"{u.scheme}://{u.netloc}", "exp": int((now or time.time()) + 12 * 3600), "sub": subject}
    head = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    body = b64u(json.dumps(claims, separators=(",", ":")).encode())
    r, s = decode_dss_signature(_priv_from_b64(priv_b64).sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
    return f"vapid t={head}.{body}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}, k={pub_b64 or public_from_private(priv_b64)}"


def _send_builtin(sub: dict, data: bytes, priv: str, pub: str, ttl: int = TTL_S, urgency: str = "high") -> int:
    body = encrypt(data, sub["keys"]["p256dh"], sub["keys"]["auth"])
    req = urllib.request.Request(sub["endpoint"], data=body, method="POST", headers={
        "Content-Encoding": "aes128gcm", "Content-Type": "application/octet-stream", "TTL": str(int(ttl)),
        "Urgency": urgency, "Authorization": vapid_header(sub["endpoint"], priv, pub)})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return int(r.status)
    except urllib.error.HTTPError as e:
        return int(e.code)


def _send_pywebpush(sub: dict, data: bytes, priv: str, pub: str, ttl: int = TTL_S, urgency: str = "high") -> int:
    from pywebpush import WebPushException, webpush
    try:
        r = webpush(subscription_info=sub, data=data, vapid_private_key=priv, vapid_claims={"sub": SUBJECT},
                    ttl=int(ttl), headers={"Urgency": urgency}, timeout=15)
        return int(getattr(r, "status_code", 201))
    except WebPushException as e:
        return int(getattr(getattr(e, "response", None), "status_code", 0) or 0)


def sender_name() -> str:
    try:
        import pywebpush  # noqa: F401
        return "pywebpush"
    except Exception:
        return "built-in"


def _sender():
    return _send_pywebpush if sender_name() == "pywebpush" else _send_builtin


def send(payload: dict, cfg=None, sender=None) -> dict:
    """One notice to every subscription: {"sent", "devices", "gone": [ids], "errors"}; never raises. gone = the push service
    answered 403/404/410 (expired, or made for another key): the app subscribes again on its next open."""
    c = cfg or config()
    if not enabled(c):
        return {"sent": 0, "devices": len(c["subs"]), "skipped": "not configured"}
    if SEALED and sender is None:
        return {"sent": 0, "devices": len(c["subs"]), "skipped": "PC self-test child: no real push"}
    send_one = sender or _sender()
    data = wire(payload)
    out = {"sent": 0, "devices": len(c["subs"]), "gone": [], "errors": []}
    for sub in c["subs"]:
        sid = endpoint_id(sub["endpoint"])
        try:
            code = int(send_one(sub, data, c["private"], c["public"]))
        except Exception as e:
            out["errors"].append(f"{sid}: {e.__class__.__name__}")
            continue
        if 200 <= code < 300:
            out["sent"] += 1
        elif code in (403, 404, 410):
            out["gone"].append(sid)
        else:
            out["errors"].append(f"{sid}: HTTP {code}")
    return out


# ---------------------------------------------------------------------------------------------- de-duplication
class Notifier:
    """Sends each notice once by its key ("fill:<entry_t>", "out:<entry_t>": the same key for the cloud and the PC).
    keys: keys already sent (the cloud keeps them in state.json); path: a JSON file of them (the PC: data/push_sent.json);
    relay: skip a trade notice the other side already marked as sent, and mark ours. sender(sub, data, priv, pub) -> HTTP
    status, for tests."""

    def __init__(self, keys=None, path: str | None = None, sender=None, cfg=None, relay: Relay | None = None, src: str = "",
                 keep: int = 600):
        self.path, self.sender, self.cfg, self.relay, self.src, self.keep = path, sender, cfg, relay, src, keep
        self.sent: dict = {str(k): float(v) for k, v in _read_json(path).items()} if path else {}
        for k in keys or []:
            self.sent.setdefault(str(k), time.time())
        self.log: list = []

    def seen(self, payload: dict) -> bool:
        return str(payload["key"]) in self.sent

    def claim(self, payload: dict) -> bool:
        """Mark the notice's key as sent unless it already was: True = this caller sends it (one notice, one sender, even when
        two paths or threads see the same trade at once)."""
        with _lock:
            k = str(payload["key"])
            if k in self.sent:
                return False
            self.sent[k] = time.time()
            if len(self.sent) > self.keep:
                for old in sorted(self.sent, key=self.sent.get)[: len(self.sent) - self.keep]:
                    self.sent.pop(old, None)
            self._save()
            return True

    def mark(self, payload_or_key):
        self.sent[str(payload_or_key["key"] if isinstance(payload_or_key, dict) else payload_or_key)] = time.time()

    def notify(self, payload: dict, push_it: bool = True, other_sent: set | None = None) -> dict:
        """Send unless already sent (here, or by the other side per the relay). The key is marked even when push is not set
        up, so nothing is ever sent hours late. push_it False = record only (the app-only notices)."""
        with _lock:
            k = str(payload["key"])
            if k in self.sent:
                return {"dup": True, "key": k}
            self.sent[k] = time.time()
            if len(self.sent) > self.keep:
                for old in sorted(self.sent, key=self.sent.get)[: len(self.sent) - self.keep]:
                    self.sent.pop(old, None)
            self._save()
        if not push_it:
            return {"sent": 0, "key": k, "skipped": "app only"}
        trade = payload.get("kind") in ("fill", "outcome")
        if other_sent is None and trade and self.relay is not None and enabled(self.cfg):
            other_sent = self.relay.sent_keys()
        if other_sent and k in other_sent:
            return {"sent": 0, "dup": True, "key": k, "by": "other side"}
        try:
            res = send(payload, cfg=self.cfg, sender=self.sender)
        except Exception as e:
            res = {"sent": 0, "errors": [e.__class__.__name__]}
        res["key"] = k
        if res.get("sent") and trade and self.relay is not None:
            self.relay.post({"le": "sent", "key": k, "src": self.src, "t": int(time.time())})
        self.log.append({"t": int(time.time()), "key": k, "title": payload.get("title"),
                         **{x: res.get(x) for x in ("sent", "gone", "errors", "skipped")}})
        del self.log[:-50]
        return res

    def keys(self) -> list:
        return sorted(self.sent, key=self.sent.get)

    def _save(self):
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.sent, fh)
            from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
            _fs_replace(tmp, self.path)
        except Exception:
            pass


# ---------------------------------------------------------------------------------------------- PC side
_PC = {"notifier": None, "sync": None, "sync_t": 0.0, "sync_err": None}
SYNC_EVERY_S = 20 * 60


SYNC_RETRY_S = 120                     # after a failed fetch: try again in 2 min (was: 20 min with nothing)
SYNC_CACHE_PATH = os.path.join(ROOT, "data", "push_pc_sync.json")   # the last good box + subs (gitignored; the box stays
                                                                     # sealed to the PC's own key, like on the branch)
if SEALED:
    SYNC_CACHE_PATH = os.path.join(_tempfile.gettempdir(), "le_selftest_push_pc_sync.json")


def _sync_cache_save(path, box, subs):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"t": int(time.time()), "box": box, "subs": subs}, fh)
        from .fsutil import replace as _fs_replace
        _fs_replace(tmp, path)
    except Exception:
        pass


def _sync_cache_load(path, mine) -> dict | None:
    try:
        c = _read_json(path)
        if not c or not (c.get("box") or c.get("subs")):
            return None
        return {"private": unseal(c["box"], mine).decode() if c.get("box") and mine else None, "subs": list(c.get("subs") or []),
                "cached": int(c.get("t") or 0)}
    except Exception:
        return None


def pc_sync(force: bool = False, fetch=None, key_path: str | None = None, cache_path: str | None = None) -> dict:
    """The VAPID key + subscriptions the cloud shares with this PC (state.json on the private dashboard branch: push_pc.box
    sealed to the PC's heartbeat key, push_subs). Cached 20 min. fetch() -> state dict, for tests. Never raises.
    2026-10-29: a failed fetch (internet blip, the GitHub login on the PC expired) keeps the last good answer (this process,
    else data/push_pc_sync.json) and tries again in 2 min, so the PC's phone pushes (entries, exits, risk) keep going;
    before, the PC sent nothing for 20 min after a blip and nothing at all with a dead login. cache_path: the file (the
    real fetch uses SYNC_CACHE_PATH; a test's fetch only when it passes one)."""
    if not force and fetch is None and _PC["sync"] is not None and time.time() - _PC["sync_t"] < SYNC_EVERY_S:
        return _PC["sync"]
    if SEALED and fetch is None:                 # PC self-test child: no GitHub fetch, no key
        return {"private": None, "subs": []}
    cpath = cache_path or (SYNC_CACHE_PATH if fetch is None else None)
    kp = key_path or PC_KEY_PATH
    out = {"private": None, "subs": []}
    mine = None
    try:
        mine = _read_json(kp).get("private")
        if fetch is not None:
            st = fetch()
        else:
            from . import nogithub
            if nogithub.active():            # GitHub-free mode: origin is gone (2026-11-08); the last good copy, no fetch
                raise RuntimeError("GitHub-free mode")
            import subprocess
            from .heartbeat import _NET_CFG, _git_env, run_cmd    # (2026-11-03) no Windows pipe hang on a stuck fetch
            r = run_cmd(["git", *_NET_CFG, "fetch", "-q", "--depth", "1", "origin", "dashboard"], cwd=ROOT, timeout=60, env=_git_env())
            if r.returncode:
                raise RuntimeError("no dashboard branch")
            r = subprocess.run(["git", "show", "FETCH_HEAD:state.json"], cwd=ROOT, capture_output=True, text=True, timeout=30)
            st = json.loads(r.stdout) if not r.returncode else {}
    except Exception as e:                   # the fetch failed: keep the last good answer, ask again in 2 min
        _PC["sync_err"] = e.__class__.__name__
        last = (_PC.get("good") or {}).get(kp) or (_sync_cache_load(cpath, mine) if cpath else None)
        if last:
            out = dict(last, stale=True)
        _PC["sync"], _PC["sync_t"] = out, time.time() - max(0, SYNC_EVERY_S - SYNC_RETRY_S)
        return out
    try:
        box = ((st or {}).get("push_pc") or {}).get("box")
        if box and mine:
            out["private"] = unseal(box, mine).decode()
        out["subs"] = [r["sub"] for r in (st or {}).get("push_subs") or [] if r.get("sub")]
        _PC["sync_err"] = None
        if cpath and (box or out["subs"]):
            _sync_cache_save(cpath, box, out["subs"])
        if out["private"] or out["subs"]:
            _PC.setdefault("good", {})[kp] = out
    except Exception as e:                   # e.g. another machine's key cannot open the box: nothing to fall back to
        _PC["sync_err"] = e.__class__.__name__
    _PC["sync"], _PC["sync_t"] = out, time.time()
    return out


# ---------------------------------------------------------------------------------------------- the PC's own key + Olympus
# Owner 2026-11-19: "I want notifications on my phone." The GitHub account behind the cloud monitor was suspended on Nov 8, so the
# cloud's key hand-off (pc_sync above) is gone for good. The PC owns its push key now; no cloud and no GitHub in the loop:
#   key      data/push.json "vapid_private" (gitignored), made once on the PC (own_key). Its PUBLIC half, the PC's box key
#            (data/push_pc_key.json) and short ids of the phones it has ride the PC's 15-minute status core post as "wp" (app_block,
#            ~230 bytes, no extra ntfy post; tools/pc_report.py).
#   phone    Olympus (tools/web_public/jarvis/push-ui.js): "Allow notifications" subscribes with that key, seals the subscription to
#            the box key (only this PC can open it: ECDH P-256 + HKDF-SHA256 "le-push-sub-v1" + AES-GCM) and posts it to the free
#            relay topic (tools/web_public/push_relay.json). The phone's own posts; the PC only reads the relay.
#   intake   the PC's 5-minute ops task (engine/alerts_plus.ops_tick already reads the relay) -> intake(): the phone joins
#            data/push.json "devices" and gets ONE welcome push; sealed "test" / "unsub" requests are proved with the phone's own
#            subscription secret. A phone that changes key / is deleted answers 403/404/410 and is dropped.
#   send     pc_notify (every real-account entry and exit the moment the bot routes / sees it), tools/pc_report.py (the 15-minute
#            report's alerts) and pc_send_now go to the phones first; the private ntfy alert topic stays the backup: an alert goes
#            there only when no phone took it, so one phone never gets the same alert twice.
# Without `cryptography` nothing here runs (no key, no "wp", no intake) and every alert goes to ntfy exactly as before.
OLYMPUS_URL = "https://dcondax1-wq.github.io/jarvis/"
SUB_INFO = b"le-push-sub-v1"
MAX_DEVICES = 5
DONE_KEEP_S = 2 * 86400              # sealed relay requests already handled (the relay keeps ~12 h; the ops task reads it every 5 min)
SUB_MAX_AGE_S = 3 * 86400            # a sealed request older (or newer) than this is ignored
_B64_87 = re.compile(r"^[A-Za-z0-9_-]{87}$")


def crypto_ok() -> bool:
    try:
        from cryptography.hazmat.primitives.asymmetric import ec  # noqa: F401
        return True
    except Exception:
        return False


def own_key(path: str | None = None, make: bool = True) -> dict | None:
    """The PC's own VAPID key {"private", "public"} from data/push.json ("vapid_private"), made once when missing (make). A broken
    key there is set aside ("vapid_private_bad") and a new one made: the phones subscribe again by themselves. None without
    `cryptography` or when the file cannot be written. Never raises; callers never print or post the private key."""
    path = path or CONFIG_PATH
    try:
        f = _read_json(path)
        priv = str(f.get("vapid_private") or "").strip()
        if priv:
            try:
                return {"private": priv, "public": public_from_private(priv)}
            except ValueError:
                if not make:
                    return None
        if not make:
            return None
        priv, pub = generate_keys()
        cur = _read_json(path)                         # read again: another PC task may have just made one
        old = str(cur.get("vapid_private") or "").strip()
        if old and old != str(f.get("vapid_private") or "").strip():
            return own_key(path, make=False)
        if old:
            cur["vapid_private_bad"] = old
        cur.update(vapid_private=priv, vapid_made=int(time.time()))
        _write_private(path, cur)
        return {"private": priv, "public": pub}
    except Exception:
        return None


def pc_config(sync=None, path: str | None = None) -> dict:
    """The PC's push set-up: its own key (own_key) + the phones in data/push.json "devices" made for it + any manual codes.
    sync: an answer of the old cloud hand-off (pc_sync; tests and old set-ups) instead."""
    if sync is not None:
        return config(private=sync.get("private"), subs_extra=sync.get("subs"))
    path = path or CONFIG_PATH
    own_key(path)
    c = config(path=path)                              # LE_VAPID_PRIVATE (if ever set) > data/push.json (the PC's own key)
    rows = [d for d in _read_json(path).get("devices") or [] if isinstance(d, dict) and d.get("sub")]
    mine = [d["sub"] for d in rows if not d.get("key") or d.get("key") == c["public"]]
    c["subs"] = parse_subs(c["subs"] + mine)
    return c


def app_block(path: str | None = None, key_path: str | None = None) -> dict | None:
    """What the phone needs from the PC's status post, public by design: k = the VAPID public key (the phone subscribes with it),
    b = the PC's box key (the phone seals its subscription to it), d = 8-character ids of the phones the PC sends to (the phone says
    "on" when it sees its own). None without `cryptography` (then only the ntfy alerts go out). Never raises."""
    try:
        if SEALED:
            return None
        c = pc_config(path=path)
        b = pc_public_key(key_path)
        if not (c.get("public") and b):
            return None
        return {"k": c["public"], "b": b, "d": sorted({endpoint_id(s["endpoint"])[:8] for s in c["subs"]})[:2 * MAX_DEVICES]}
    except Exception:
        return None


def app_block_ok(wp) -> bool:
    """A "wp" block as app_block makes it (only public keys and short hex ids: safe to post as is)."""
    return (isinstance(wp, dict) and set(wp) == {"k", "b", "d"} and all(isinstance(wp[x], str) and _B64_87.match(wp[x]) for x in "kb")
            and isinstance(wp["d"], list) and all(isinstance(i, str) and re.fullmatch(r"[0-9a-f]{8}", i) for i in wp["d"]))


def _devices(path) -> list:
    return [d for d in _read_json(path).get("devices") or [] if isinstance(d, dict) and d.get("id") and d.get("sub")]


def drop_gone(ids, path: str | None = None) -> int:
    """Forget the phones the push service called gone (403 / 404 / 410: deleted, or made for another key). Never raises."""
    path = path or CONFIG_PATH
    try:
        ids = {str(i) for i in ids or ()}
        f = _read_json(path)
        rows = f.get("devices") or []
        keep = [d for d in rows if not (isinstance(d, dict) and d.get("id") in ids)]
        if len(keep) != len(rows):
            f["devices"] = keep
            _write_private(path, f)
        return len(rows) - len(keep)
    except Exception:
        return 0


def _hm_et(t) -> str:
    try:
        return _et_dt(t).strftime("%I:%M %p ET").lstrip("0")
    except Exception:
        return ""


def welcome_payload(now=None) -> dict:
    now = int(now or time.time())
    p = text_payload("PC", "test", "Olympus notifications are on",
                     "This phone now gets every trade (entry and exit, with the account name) and the important alerts from your PC.",
                     key=f"welcome:{now}", t=now, url="#board")
    p["tag"] = "le-welcome"
    return p


def test_payload(now=None) -> dict:
    now = int(now or time.time())
    p = text_payload("PC", "test", "Test from your PC", f"Notifications work: your PC sent this at {_hm_et(now)}.", key=f"test:{now}",
                     t=now, url="#board")
    p["tag"] = "le-test"
    return p


# PAIRING (day-security2 2026-11-20, LEAD_WIRES W4). The PC's box key and VAPID key are public (every status post's "wp"), so before
# this anyone could seal a "sub" and get every real-account trade alert, and five of them pushed the owner's phone off the list.
#   * the phones already on the list stay, with no code (the owner does nothing); a phone sending its own subscription again stays
#   * a NEW phone needs the one-time 8-digit code: the PC sends it to the phones already on the list and the private alert topic
#     the first time an unknown phone asks (then at most every PAIR_TELL_S), with "type it only on a phone you are holding"
#   * the very first phone of a PC that never had one joins without a code (nothing to send the code to yet); after that, never
#   * a list full of phones heard from in the last RECENT_S never pushes one out for a newcomer (the newcomer waits)
# THE CODE IS OFF until the phone side ships (redteam 2026-11-21): tools/web_public/jarvis/push-ui.js has no way to type it yet
# (LEAD_WIRES W4: the sealed body's "pair" field + the input on the 'waiting' card). Until then the owner's own phone with a new
# endpoint (Home Screen app re-added, notification permission reset, a new VAPID key) would be a "new phone" that can never join,
# and lose every app-only notice. Off = a new phone joins as before the code existed; the no-eviction guard below stays ON either
# way (a list full of phones heard from in RECENT_S never pushes one out for a newcomer). Flip to True IN THE SAME PUBLISH as the
# push-ui.js pair input (and its jarvis / sw cache bump).
PAIR_CODE_ON = False
PAIR_DIGITS = 8
PAIR_TELL_S = 6 * 3600
PAIR_BAD_MAX = 30                    # wrong codes in one UTC day; then no new phone joins until tomorrow
RECENT_S = 14 * 86400


def pair_code(f: dict, now: int, fresh: bool = False) -> str:
    """The current one-time code in f["pair"] (made when missing or when fresh). Mutates f; the caller writes it."""
    import secrets as _sec
    p = f.get("pair") if isinstance(f.get("pair"), dict) else {}
    if fresh or not re.fullmatch(r"\d{%d}" % PAIR_DIGITS, str(p.get("code") or "")):
        p = {"code": str(_sec.randbelow(10 ** PAIR_DIGITS)).zfill(PAIR_DIGITS), "made": now, "told": 0, **{k: p.get(k) for k in ("bad", "bad_day") if p.get(k)}}
    f["pair"] = p
    return p["code"]


def pair_payload(code: str, ua: str, now=None, full: bool = False) -> dict:
    now = int(now or time.time())
    if full:
        body = ("A new phone asked for your trade alerts, but your list is full (%d phones heard from in the last 14 days). "
                "Turn one off in its Olympus app first." % MAX_DEVICES)
    else:
        body = (f"A new phone ({ua or 'unknown'}) asked for your trade alerts. If it is yours, type {code} on it. "
                "Type it only on a phone you are holding; if it is not yours, ignore this and nothing happens.")
    p = text_payload("PC", "test", "New phone wants your alerts", body, key=f"pair:{now}", t=now, url="#board")
    p["tag"] = "le-pair"
    return p


def joined_payload(rows: list, now=None) -> dict:
    """'A new phone now gets your trade alerts' (PAIR_CODE_ON off): who (the browser words, 8-hex id) and how to remove it."""
    now = int(now or time.time())
    who = "; ".join(f"{str(r.get('ua') or 'a phone')[:30]} (id {str(r.get('id'))[:8]})" for r in rows[:3]) + (" ..." if len(rows) > 3 else "")
    body = (f"New phone(s) now get your trade alerts: {who}. If one is not yours, on the PC run: "
            f"python -m engine.push --forget {str(rows[0].get('id'))[:8] if rows else '<id>'}")
    p = text_payload("PC", "test", "New phone added to your alerts", body, key=f"joined:{now}", t=now, url="#board")
    p["tag"] = "le-joined"
    return p


def forget(id8: str, path: str | None = None) -> list:
    """Remove the phone(s) whose id starts with id8 (at least 6 hex characters) from data/push.json. -> the ids removed."""
    path = path or CONFIG_PATH
    k = re.sub(r"[^0-9a-f]", "", str(id8 or "").lower())
    if len(k) < 6:
        return []
    f = _read_json(path)
    devs = [d for d in f.get("devices") or [] if isinstance(d, dict)]
    gone = [d["id"] for d in devs if str(d.get("id", "")).startswith(k)]
    if gone:
        f["devices"] = [d for d in devs if d.get("id") not in gone]
        _write_private(path, f)
    return gone


def _tell_owner(p: dict, c: dict, rows: list, sender=None, path=None, ntfy=None) -> int:
    """The pairing notice to the phones already on the list and (on the real PC only) the private ntfy alert topic. Never raises."""
    n = 0
    try:
        if rows:
            n += int(app_send(p, cfg=dict(c, subs=[r["sub"] for r in rows]), sender=sender, path=path).get("sent") or 0)
    except Exception:
        pass
    try:
        if ntfy is None and sender is None:          # the real PC: also the private topic (only the owner knows its name)
            from . import notify as _n
            cfg = _n.alert_cfg()
            if cfg:
                n += int(bool(_n._post(cfg["ntfy"], cfg["topic"], {"title": p.get("title") or "New phone", "body": p.get("body") or "",
                                                                   "priority": "high", "tags": "iphone"})))
        elif callable(ntfy):
            n += int(bool(ntfy(p)))
    except Exception:
        pass
    return n


def intake(msgs, now=None, path: str | None = None, key_path: str | None = None, sender=None, ntfy=None) -> dict:
    """The ops task's relay read (every 5 min): the phones' sealed {"le": "sub" | "unsub" | "test", "v": 2, "box"} requests.
    sub    a subscription made with the PC's own key joins data/push.json "devices" (the newest MAX_DEVICES phones heard from)
           and that phone alone gets ONE welcome push;
    unsub  removes the phone, test sends it one test push; both only with the phone's own subscription secret inside the box.
    Each request once (its hash in "done", 2 days), never one older than 3 days. -> {"added", "removed", "tests", "sent",
    "ignored"}. Never raises; posts nothing to ntfy."""
    out = {"added": [], "removed": [], "tests": [], "sent": 0, "ignored": 0}
    try:
        import hmac as _hmac
        now = int(time.time() if now is None else now)
        path = path or CONFIG_PATH
        reqs = [m for m in msgs or [] if isinstance(m, dict) and m.get("le") in ("sub", "unsub", "test") and m.get("v") == 2
                and isinstance(m.get("box"), str) and 100 < len(m["box"]) < 6000]
        if not reqs:
            return out
        c = pc_config(path=path)
        pc_public_key(key_path)                          # the box key exists before the first phone can seal to it
        mine = _read_json(key_path or PC_KEY_PATH).get("private")
        if not c.get("public") or not mine:
            out["skipped"] = "no key on this PC (cryptography missing?)"
            return out
        f = _read_json(path)
        before = {d["id"] for d in _devices(path)}
        devs = {d["id"]: dict(d) for d in _devices(path)}
        done = {k: v for k, v in (f.get("done") or {}).items() if isinstance(v, (int, float)) and now - v < DONE_KEEP_S}
        pair_on = bool(f.get("pair_on")) or bool(devs)  # a PC that has (or had) a phone: new phones need the code
        pf = {"pair": f.get("pair")}
        code = pair_code(pf, now)
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        if (pf["pair"].get("bad_day") or "") != day:
            pf["pair"].update(bad=0, bad_day=day)
        asked = []                                       # unknown phones that asked without the right code: (ua, full?)
        for m in sorted(reqs, key=lambda x: x.get("_t", 0)):
            h = hashlib.sha256(m["box"].encode()).hexdigest()[:16]
            if h in done:
                continue
            done[h] = now
            try:
                body = json.loads(unseal(m["box"], mine, SUB_INFO).decode("utf-8"))
                kind, t = body.get("le"), int(body.get("t") or 0)
            except Exception:
                out["ignored"] += 1
                continue
            if kind != m.get("le") or abs(now - t) > SUB_MAX_AGE_S:
                out["ignored"] += 1
                continue
            if kind == "sub":
                subs = parse_subs(body.get("sub"))
                if not subs or body.get("key") != c["public"]:
                    out["ignored"] += 1                  # junk, or made for an old key (the phone subscribes again by itself)
                    continue
                sid = endpoint_id(subs[0]["endpoint"])
                ua = re.sub(r"[^A-Za-z0-9 .()/-]", "", str(body.get("ua") or ""))[:40]
                if sid not in devs and pair_on:          # a NEW phone: the one-time code (PAIR_CODE_ON), a free place
                    given = re.sub(r"\D", "", str(body.get("pair") or ""))
                    if PAIR_CODE_ON and (int(pf["pair"].get("bad") or 0) >= PAIR_BAD_MAX or not given
                                         or not _hmac.compare_digest(given, code)):
                        if given:
                            pf["pair"]["bad"] = int(pf["pair"].get("bad") or 0) + 1
                        out["ignored"] += 1
                        out["unpaired"] = out.get("unpaired", 0) + 1
                        asked.append((ua, False))
                        continue
                    recent = [d for d in devs.values() if now - int(d.get("seen") or 0) < RECENT_S]
                    if len(recent) >= MAX_DEVICES:
                        out["ignored"] += 1
                        out["full"] = out.get("full", 0) + 1
                        asked.append((ua, True))
                        continue
                    if PAIR_CODE_ON:
                        code = pair_code(pf, now, fresh=True)  # one time: the next new phone needs a new code
                row = devs.get(sid) or {"id": sid, "since": now}
                if sid not in devs and sid not in out["added"]:
                    out["added"].append(sid)
                    pair_on = True
                row.update(sub=subs[0], key=c["public"], seen=now, ua=ua)
                devs[sid] = row
                continue
            sid, row = str(body.get("id") or ""), devs.get(str(body.get("id") or ""))
            if not row or not _hmac.compare_digest(str(body.get("auth") or ""), str(row["sub"]["keys"]["auth"])):
                out["ignored"] += 1
                continue
            if kind == "unsub":
                devs.pop(sid, None)
                out["removed"].append(sid)
            elif sid not in out["tests"]:
                out["tests"].append(sid)
        keep = sorted(devs.values(), key=lambda d: d.get("seen") or 0)[-MAX_DEVICES:]
        out["removed"] += [i for i in devs if i not in {d["id"] for d in keep}]
        f = _read_json(path)                             # read again: the bot may have dropped a gone phone meanwhile
        now_ids = {d["id"] for d in _devices(path)}
        f["devices"] = [d for d in keep if d["id"] in now_ids or d["id"] not in before]
        f["done"] = done
        had_phones = bool(before) or bool(f.get("pair_on"))
        if pair_on:
            f["pair_on"] = f.get("pair_on") or now
        told = None
        if asked and now - int(pf["pair"].get("told") or 0) >= PAIR_TELL_S:   # no phone left: the private topic still gets it
            told = pair_payload(code, asked[-1][0], now, full=asked[-1][1])
            pf["pair"]["told"] = now
        elif not PAIR_CODE_ON and had_phones and out["added"]:
            # day-security3 2026-11-21: while the code is OFF a stranger who taps Allow on the public site joins and gets every
            # trade alert. The owner hears of EVERY new phone at once (his phones + the private topic), with the one command that
            # removes it; a flood of joins is one notice per run.
            new_rows = [d for d in f["devices"] if d["id"] in out["added"]]
            told = joined_payload(new_rows, now)
        f["pair"] = pf["pair"]
        _write_private(path, f)
        rows = {d["id"]: d for d in f["devices"]}
        if told:
            out["told"] = _tell_owner(told, c, [d for d in f["devices"] if d["id"] not in out["added"]], sender=sender, path=path, ntfy=ntfy)
        todo = [(i, welcome_payload(now)) for i in out["added"] if i in rows] + [(i, test_payload(now)) for i in out["tests"] if i in rows]
        for sid, p in todo:
            r = app_send(p, cfg=dict(c, subs=[rows[sid]["sub"]]), sender=sender, path=path)
            out["sent"] += int(r.get("sent") or 0)
    except Exception as e:
        out["error"] = e.__class__.__name__
    return out


# audit 2026-11-22 package B: the PC's critical alarms (engine/alerts_plus crit kinds, engine/guards' "le-guard" pushes: entries
# blocked, clock drift, kill switch, no-stop mismatch, room under $400) reach the phone app at once, and the private ntfy topic too
# (engine/notify.instant_problem). Not "update" (autoupdate has its own path) and not "hedge" (its own HEDGE route).
CRITICAL_KINDS = ("clock", "kill", "unprotected", "eval_floor", "freeze", "feed_stale", "ops_crit")


def critical(p: dict) -> bool:
    p = p or {}
    return p.get("kind") in CRITICAL_KINDS or p.get("tag") == "le-guard"


def _crit_ntfy(p: dict) -> str:
    """The critical alarm's private-topic copy (engine/notify.instant_problem, its own de-dup by key; the app copy already
    went out, so no_app). Never raises."""
    try:
        if p.get("silent"):
            return "silent: app only"            # a "Resolved" notice / a silent level never rings ntfy (red team 2026-11-23)
        # red team 2026-11-23: engine/alerts_plus repeats a critical alarm every 10 min (key crit:<id>:<n>) and restarts the cycle
        # when a flapping condition comes back the same day; the app's "Got it" stops those repeats, ntfy cannot. So ntfy gets
        # the FIRST notice per condition id only (the id is per day): key without the repeat number
        k = str(p.get("ack") or p.get("key") or "")
        from . import notify
        return notify.instant_problem({"key": f"crit:{k}", "title": p.get("title"), "body": p.get("body"),
                                       "code": str(p.get("kind") or "ops_crit"), "no_app": True})
    except Exception as e:  # noqa: BLE001
        return f"failed: {e.__class__.__name__}"


def pc_app_ok(p: dict) -> bool:
    """Which PC notices go to the phone (owner 2026-11-18, "important only"): every real-account entry / exit (notify_settings.json
    trade_opened / trade_closed; never Paper, Sim, BLITZ), tests, and the 15-minute report's alerts (kind "report", already filtered
    by engine/notify.apply). Every other kind (ops helper, risk, armed setups ...) only with LE_PUSH_EXTRA=1: none of them went to
    the ntfy alerts either, and several repeat what the report already says."""
    k = (p or {}).get("kind")
    if k in ("test", "report") or critical(p):
        return True
    if k in ("fill", "outcome"):
        try:
            from . import notify
            return notify.real_trade(p) and notify.on("trade_opened" if k == "fill" else "trade_closed")
        except Exception:
            return False
    return extra_on()


_TRADE_KEY = re.compile(r"^(?:fill|out):(\d+)(.*)$")


def app_trade_tag(p: dict) -> str:
    """One notification per trade AND account (two accounts can enter on the same bar): the exit replaces the entry."""
    m = _TRADE_KEY.match(str(p.get("key") or ""))
    et_, rest = (m.group(1), m.group(2)) if m else (str(int(p.get("t") or 0)), "")
    return f"t{hashlib.sha1((str(p.get('account') or '') + rest).encode()).hexdigest()[:6]}-{et_}"


def app_payload(p: dict, now=None) -> dict:
    """What Olympus shows for a PC notice: a trade gets the owner's account name and $ ("Zlarior 50K: LONG opened", "risk $368 ·
    target +$1,432 · 6 MNQ at 24,980 ..."; "Zlarior 50K: LONG closed +$605"), its own tag (the exit replaces the entry) and opens the
    NQ page; quiet hours = no sound. Other notices keep their words. Never raises."""
    q = dict(p or {})
    try:
        from . import notify
        k = q.get("kind")
        if k == "fill":
            m = notify.entry_message(q, now=now)
            q.update(title=m["title"], body=m["body"], silent=m["priority"] == "low")
        elif k == "outcome":
            m = notify.exit_message(q, now=now)
            q.update(title=m["title"], body=m["body"], silent=m["priority"] == "low")
        if k in ("fill", "outcome"):
            q.update(tag=app_trade_tag(p), url="#nq")
        elif str(q.get("url") or "").startswith("#/"):      # the old app's routes (#/activity, #/today ...): Olympus's Board
            q["url"] = "#board"
        q["key"] = notify.mask_ids(q.get("key"))           # an extra account's key can end in its id: only the last 4 travel
    except Exception:
        pass
    return q


def report_payload(m: dict) -> dict:
    """A 15-minute report alert (tools/pc_report.py: key, title, body, priority) for Olympus: the same words, one tag per thing (a
    trade's close replaces its open, "Back to normal" replaces its problem) and the page it opens. Quiet hours = no sound."""
    key = str((m or {}).get("key") or "")
    try:
        from . import notify
        kind = m.get("kind") or notify.kind_of(key)
    except Exception:
        kind = "other"
    parts = key.split(":")
    if key.startswith(("open:", "close:")) and len(parts) >= 3:
        tag = f"r-{re.sub(r'[^A-Za-z0-9_-]', '', parts[1])[:24]}-{parts[-1]}"
    elif key.startswith(("cond:", "back:")) and len(parts) >= 2:
        tag = f"le-cond-{re.sub(r'[^A-Za-z0-9_-]', '', parts[1])[:24]}"
    else:
        tag = f"le-{str(kind).replace('_', '-')[:20]}-{hashlib.sha1(key.encode()).hexdigest()[:6]}"
    url = "#nq" if kind in ("trade_opened", "trade_closed", "account_status", "eval_milestones", "room_low") else "#board"
    try:
        from . import notify as _n
        wkey = _n.mask_ids(key)
    except Exception:
        wkey = re.sub(r"\d{5,}", "", key)
    return {"kind": "report", "key": f"rep:{wkey}", "t": int((m or {}).get("t") or time.time()), "title": str(m.get("title") or "Olympus")[:120],
            "body": str(m.get("body") or "")[:600], "tag": tag, "url": url, "silent": (m or {}).get("priority") in ("low", "min")}


def app_send(payload: dict, cfg=None, sender=None, path: str | None = None) -> dict:
    """One notice to the phones with the PC's own key; the ones the push service calls gone are forgotten. {"sent", "devices",
    "gone", "errors"}; never raises, never posts to ntfy."""
    try:
        c = cfg or pc_config(path=path)
        if not enabled(c):
            return {"sent": 0, "devices": len(c.get("subs") or []), "skipped": "no phone"}
        if SEALED and sender is None:
            return {"sent": 0, "skipped": "PC self-test child: no real push"}
        r = send(payload, cfg=c, sender=sender)
        if r.get("gone"):
            drop_gone(r["gone"], path)
        return r
    except Exception as e:
        return {"sent": 0, "errors": [e.__class__.__name__]}


def pc_notifier() -> Notifier:
    if _PC["notifier"] is None:
        # no relay: the cloud that read its "sent" markers is gone, and every marker would be one more ntfy publish of the PC's IP
        _PC["notifier"] = Notifier(path=SENT_PATH, relay=None, src="pc")
    return _PC["notifier"]


NO_TOPIC = "no private alert topic"         # engine/notify._instant_send's answer on a PC without OLYMPUS_HOME/ntfy.json
# One more try of an instant ntfy trade alert the 15-minute report cannot send under the account's own name (skeptic 2026-11-20):
# an extra LIT account (":<id>": the 25K #2, the Rapid's LIT lane; the report's one "lit" row is titled the 50K) or the Rapid's ATLAS
# lane (":acctr": the report has no row for it). The 50K (no suffix) and ATLAS (":acctb") get the report's own ntfy copy instead.
NTFY_RETRY_S = 60
NTFY_RETRY_ACCTS = ("", "acctb", "acctc")   # key_acct values NOT retried here (the report covers them; BLITZ is never a real trade)


def _retry_owed(payload: dict, said) -> bool:
    """Whether an instant ntfy trade alert gets one more try (NTFY_RETRY_S later, _pc_send): ntfy refused it or the post failed
    (never "no topic", "... is off" or "already sent") and its key belongs to an extra LIT account or the Rapid's ATLAS lane."""
    try:
        from . import notify
        s = str(said or "")
        if not s.startswith(("failed", "ntfy did not take it")):
            return False
        return notify.key_acct((payload or {}).get("key")) not in NTFY_RETRY_ACCTS
    except Exception:
        return False


def _pc_send(payload, sender=None, ntfy=None, ntfy_exit=None, retry_s=None) -> dict:
    """pc_notify's worker thread. A real trade's ENTRY and EXIT go to BOTH routes: the phone app (Web Push) AND the private ntfy alert
    topic (engine/notify.instant_entry / instant_exit). Until 2026-11-20 ntfy got them only when no phone took them, and "took" only
    meant Apple / Google accepted the push, not that the phone showed it; that "accepted" also made the 15-minute report skip its
    copy. ATLAS's 03:45 ET entry and 07:10 ET +$514 close that day reached no phone, most likely that way (unconfirmed: the PC's push
    logs were not read). A phone-only delivery is recorded (engine/notify.instant_record app_only) so the report sends just its ntfy
    copy (or nothing, without a topic). notify_settings.json trade_routes (engine/notify.trade_routes): "both" (default), "olympus"
    (the app first, ntfy only when no phone took it) or "ntfy" (ntfy first, the app only when ntfy did not take it).
    retry_s (pc_notify: NTFY_RETRY_S; None = no retry, the tests' default): an extra account's instant ntfy alert that ntfy refused is
    tried once more after retry_s seconds in this same worker thread (order routing never waits on it), _retry_owed.
    Every other notice: the phone app only, as before. Each trade alert's answers -> logs/notify/trade_alerts.jsonl. -> what happened
    (tests). Never raises."""
    res: dict = {}
    n = None
    k = payload.get("kind")
    trade = k in ("fill", "outcome")
    app_ok = True

    tried = []

    def _app() -> dict:
        tried.append(1)
        try:
            return app_send(app_payload(payload), sender=sender) if pc_app_ok(payload) else {"sent": 0, "skipped": "not for the phone"}
        except Exception as e:  # noqa: BLE001
            return {"sent": 0, "errors": [e.__class__.__name__]}

    try:
        n = pc_notifier()
        if not n.claim(payload):                 # another path / thread already has this notice (same key)
            return {"dup": True}
        # engine/alert_bus (day-alerts 2026-11-21): when the owner set it up (ALERTS_SETUP.bat), a real trade's entry / exit and a hedge
        # notice go to Telegram / Discord first, with ntfy and this app as its fallbacks; off / not set up = the path below, exactly
        bus = _bus_send(payload) if (ntfy is None and ntfy_exit is None and sender is None) else None
        if bus and bus.get("bus") in ("queued", "sent", "dup"):   # the bus took it; "off" / "bad" = the old path below (redteam 2026-11-21)
            return bus
    except Exception as e:
        res, app_ok = {"sent": 0, "errors": [e.__class__.__name__]}, False
    if not trade:
        if app_ok:
            res = _app()
        if critical(payload) and ntfy is None and sender is None:
            res["ntfy"] = _crit_ntfy(payload)
        if k == "risk" and str(payload.get("key") or "").startswith("hedge"):
            try:                                 # drill 2026-11-21: HEDGE BLOCKED reached no phone without LE_PUSH_EXTRA (the app took
                from . import notify             # only trades); now the private ntfy topic too (problems: rings at night)
                res["ntfy"] = notify.instant_problem({"key": str(payload["key"]), "code": "hedge", "title": payload.get("title"),
                                                      "body": payload.get("body")})
            except Exception:  # noqa: BLE001
                pass
    else:
        try:
            from . import notify
            what = "entry" if k == "fill" else "exit"
            mode = notify.trade_routes()

            def _ntfy() -> str:                  # owner 2026-11-18 entries, 2026-11-20 exits ("and closed, results of it"): at once
                return ((ntfy or notify.instant_entry) if k == "fill" else (ntfy_exit or notify.instant_exit))(dict(payload))

            def _ntfy_retry() -> str:            # the same alert once more: an app-only record does not count as "already sent"
                return ((ntfy or notify.instant_entry) if k == "fill" else (ntfy_exit or notify.instant_exit))(dict(payload, retry=True))
            if mode == "ntfy":                   # ntfy first; the app only when ntfy did not take it
                said = _ntfy()
                if said == "sent":
                    if app_ok:
                        res = {"sent": 0, "skipped": "ntfy has it (trade_routes ntfy)"}
                else:
                    if app_ok:
                        res = _app()
                    if res.get("sent"):
                        notify.instant_record(payload, what, app_only=True)
                res["ntfy"] = said
            else:
                if app_ok:
                    res = _app()
                if mode == "olympus" and res.get("sent"):
                    notify.instant_record(payload, what)      # one route asked for: the report skips it entirely (the old rule)
                    res["ntfy"] = "skipped: the phone app has it (trade_routes olympus)"
                else:
                    res["ntfy"] = _ntfy()
                    if res.get("sent") and res["ntfy"] != "sent":
                        # the phone app has it, ntfy not (refused, or no topic in THIS process): the report sends only its ntfy copy, if
                        # its own config has a topic (the 15-minute task may see one the server does not), never the app copy again
                        notify.instant_record(payload, what, app_only=True)
            if retry_s is not None and _retry_owed(payload, res.get("ntfy")):
                # the report cannot send this ntfy copy under the account's own name: one more try in this worker thread (the
                # instant record above already tells the report what the app got). Success records "entries" / "exits"
                # (notify._instant_send's retry flag), so the report skips the row entirely.
                time.sleep(max(0.0, float(retry_s)))
                again = _ntfy_retry()
                res["ntfy_first"], res["ntfy"] = res.get("ntfy"), again
        except Exception:
            if app_ok and not tried:             # never lose the phone app copy to a fault on the ntfy side
                res = _app()
    try:
        if n is not None:
            from . import notify as _n
            n.log.append({"t": int(time.time()), "key": _n.mask_ids(payload.get("key")),
                          **{x: res.get(x) for x in ("sent", "gone", "errors", "skipped", "ntfy")},
                          **({"ntfy_first": res["ntfy_first"]} if res.get("ntfy_first") else {})})
            del n.log[:-50]
    except Exception:
        pass
    if trade:
        _trade_log(payload, res)
    return res


TRADE_LOG_MAX_BYTES = 256 * 1024


def _trade_log(payload: dict, res: dict) -> None:
    """One line per trade alert in logs/notify/trade_alerts.jsonl (next to engine/notify.INSTANT_PATH, gitignored): the owner's
    account name, the masked key and what each route answered (app: sent / devices / gone / errors / skipped; ntfy: sent or why
    not). "warn" when it reached NO route. Until 2026-11-20 these answers lived only in the server's memory. No topic, no endpoint,
    no account id. Kept under TRADE_LOG_MAX_BYTES. Never raises."""
    try:
        from . import notify
        path = os.path.join(os.path.dirname(notify.INSTANT_PATH), notify.TRADE_LOG_NAME)
        row = {"t": int(time.time()), "kind": payload.get("kind"), "key": notify.mask_ids(payload.get("key")),
               "who": notify.display_name(payload) if notify.real_trade(payload) else "not a real account",
               "app": {x: res.get(x) for x in ("sent", "devices", "gone", "errors", "skipped") if res.get(x) not in (None, [], "")},
               "ntfy": res.get("ntfy"), **({"ntfy_first": res["ntfy_first"]} if res.get("ntfy_first") else {})}
        if notify.real_trade(payload) and not res.get("sent") and res.get("ntfy") != "sent" and "off" not in str(res.get("ntfy")):
            row["warn"] = "this trade alert reached NO phone (no Olympus phone took it and ntfy did not)"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            if os.path.getsize(path) > TRADE_LOG_MAX_BYTES:
                with open(path, encoding="utf-8") as fh:
                    keep = fh.readlines()[-300:]
                with open(path, "w", encoding="utf-8") as fh:
                    fh.writelines(keep)
        except OSError:
            pass
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        pass


def _bus_send(payload: dict) -> dict | None:
    """engine/alert_bus (owner 2026-11-21: Telegram / Discord first; ntfy and this app are its fallbacks): a real-account entry /
    exit, or a HEDGE BLOCKED risk notice, goes to the bus, which records the entry / exit once delivered (so the 15-minute report
    skips its copy). None = the bus is off / not set up: the old path below, exactly. Never raises."""
    try:
        from . import alert_bus as AB
        if not AB.active():
            return None
        from . import notify
        k = payload.get("kind")
        if k in ("fill", "outcome") and notify.real_trade(payload):
            what = "entry" if k == "fill" else "exit"
            p = dict(payload)
            r = AB.send(AB.from_trade(p, what), on_done=lambda res: res.get("ok") and notify.instant_record(p, what))
            return {"bus": r}
        if k == "risk" and str(payload.get("key") or "").startswith("hedge"):
            r = AB.send({"kind": "hedge_risk", "key": str(payload.get("key")), "title": payload.get("title"),
                         "body": payload.get("body"), "report": True, "dual": True})
            return {"bus": r}
    except Exception:
        return None
    return None


def pc_notify(payload: dict) -> dict | None:
    """PC side, in a background thread (the push service never delays order routing): pc_app_ok notices to the phone app; every
    real-account entry and exit also to the private ntfy alert topic (_pc_send, since 2026-11-20 whatever the app said; trade_routes
    in notify_settings.json can pick one route first). Never raises."""
    try:
        if pc_notifier().seen(payload):
            return {"dup": True}
        threading.Thread(target=_pc_send, args=(dict(payload),), kwargs={"retry_s": NTFY_RETRY_S}, name="push", daemon=True).start()
        return {"queued": True}
    except Exception:
        return None


def pc_send_now(payload: dict, sync=None, sender=None) -> dict:
    """PC side, synchronous, for a script or a scheduled task (no server thread to wait for): push one notice now. No
    de-duplication here (engine/ops_checks keeps its own keys in data/ops_state.json); pc_app_ok decides what goes. sync =
    pc_sync() result, for tests. Never raises."""
    try:
        if sync is None and not pc_app_ok(payload):
            return {"sent": 0, "skipped": "not for the phone (LE_PUSH_EXTRA=1 sends it)"}
        if critical(payload) and sync is None and sender is None:
            _crit_ntfy(payload)
        cfg = pc_config(sync)
        if not enabled(cfg):
            return {"sent": 0, "skipped": "not configured"}
        return app_send(app_payload(payload), cfg=cfg, sender=sender)
    except Exception as e:
        return {"sent": 0, "errors": [e.__class__.__name__]}


def save_pc_config(patch: dict, path: str | None = None) -> dict:
    """PC dashboard manual override (data/push.json, gitignored): a private key and/or subscription codes."""
    path = path or CONFIG_PATH
    cur = _read_json(path)
    priv = (patch.get("vapid_private") or "").strip()
    if priv:
        public_from_private(priv)                    # raises ValueError on a bad key: the API returns the message
        cur["vapid_private"] = priv
    if patch.get("subs") is not None:
        new = parse_subs(patch.get("subs"))
        if patch.get("subs") and not new:
            raise ValueError("no subscription found in that text: copy the whole code")
        cur["subs"] = new if patch.get("subs_mode") == "replace" else parse_subs((cur.get("subs") or []) + new)
    if patch.get("clear"):
        cur = {}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cur, fh, indent=1)
    return status(config(path=path))


def main(argv=None) -> int:
    """python -m engine.push --devices          the phones that get the app's alerts (8-hex id, browser, since, last seen)
       python -m engine.push --forget <id>      remove one (the first 6+ characters of its id); it stops getting alerts at once"""
    import sys as _sys
    a = list(_sys.argv[1:] if argv is None else argv)
    if a[:1] == ["--devices"]:
        rows = _devices(CONFIG_PATH)
        for d in rows:
            print(f"{str(d.get('id'))[:8]}  {str(d.get('ua') or '?')[:30]:<30}  since {time.strftime('%Y-%m-%d', time.gmtime(int(d.get('since') or 0)))}"
                  f"  seen {time.strftime('%Y-%m-%d %H:%M', time.gmtime(int(d.get('seen') or 0)))} UTC")
        print(f"{len(rows)} phone(s)")
        return 0
    if a[:1] == ["--forget"] and len(a) == 2:
        gone = forget(a[1])
        print(f"[OK] removed {len(gone)} phone(s)" if gone else "[FIX] no phone with that id (python -m engine.push --devices)")
        return 0 if gone else 1
    print(main.__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

