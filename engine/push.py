"""Web Push notifications to the phone app (the Home Screen web app at demetrades2000-coder.github.io/nq-dashboard).

Owner (2026-10-18): the only thing to do is tap "Allow" in the app; the rest is automatic. Two kinds of notice, short:
  ENTRY    title "LONG · MFFU 50K"   body "Entered 4 MNQ"
  OUTCOME  title "LONG · MFFU 50K"   body "+$1,812" | "−$366" | "$0 breakeven" | "+$212 closed 15:55"
One notification tag per trade (the outcome replaces the entry), the app icon, details in the app's Activity page.
Account label: "Paper" for the cloud paper bot, the NinjaTrader account name for PC fills (e.g. "Sim101"), live_model.json
"account": {"name": ...} (default "MFFU 50K") for a real account.

How it stays automatic (no server of our own, no copy-paste):
  relay    a free ntfy.sh topic (tools/web_public/push_relay.json, not secret). The app posts its push subscription there when
           notifications are allowed; the cloud monitor reads the topic every run and keeps the subscriptions in its own
           state (dashboard branch). The cloud and the PC post "sent" markers there, so a trade is notified once.
  key      the VAPID key pair. GitHub Secret LE_VAPID_PRIVATE when set; otherwise the cloud makes a pair on its first run and
           keeps the private key in the GitHub Actions cache (LE_VAPID_KEY_FILE, never committed, never printed). The public
           key goes to data.json; when it changes, the app subscribes again on its next open.
  PC       the PC bot gets the same key without a manual step: it publishes its own public key in the heartbeat, the cloud
           encrypts the VAPID private key to it (ECIES, state.json on the private dashboard branch) and the PC decrypts it
           with data/push_pc_key.json (gitignored), together with the subscriptions.
Manual overrides still work: LE_PUSH_SUBS (+ _2.._5) secrets, data/push.json on the PC.

Sending uses pywebpush when installed, else the built-in RFC 8291 (aes128gcm) + RFC 8292 (VAPID) sender (needs only
`cryptography`). Nothing configured = every call is a silent no-op. Never raises into the trading loops.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
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
RELAY_PATH = os.path.join(ROOT, "tools", "web_public", "push_relay.json")
APP_URL = "https://demetrades2000-coder.github.io/nq-dashboard/"
SUBJECT = os.environ.get("LE_PUSH_SUBJECT") or "https://demetrades2000-coder.github.io"   # VAPID "sub" claim: a contact URL, host only
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
    os.replace(tmp, path)


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
def seal(secret: bytes, recipient_pub_b64: str) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    rp = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b64u_dec(recipient_pub_b64))
    eph = ec.generate_private_key(ec.SECP256R1())
    key = HKDF(hashes.SHA256(), 32, None, b"le-push-pc-v1").derive(eph.exchange(ec.ECDH(), rp))
    nonce = os.urandom(12)
    return b64u(_pub_bytes(eph.public_key()) + nonce + AESGCM(key).encrypt(nonce, secret, None))


def unseal(box_b64: str, recipient_priv_b64: str) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    b = b64u_dec(box_b64)
    eph = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), b[:65])
    key = HKDF(hashes.SHA256(), 32, None, b"le-push-pc-v1").derive(_priv_from_b64(recipient_priv_b64).exchange(ec.ECDH(), eph))
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
                if isinstance(body, dict) and body.get("le") in ("sub", "unsub", "sent"):
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


def wire(payload: dict) -> bytes:
    """What goes to the phone (well under the 4 KB push limit): title, body, tag, url, kind, key, t."""
    keep = {k: payload.get(k) for k in ("title", "body", "tag", "url", "kind", "key", "t")}
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
            os.replace(tmp, self.path)
        except Exception:
            pass


# ---------------------------------------------------------------------------------------------- PC side
_PC = {"notifier": None, "sync": None, "sync_t": 0.0, "sync_err": None}
SYNC_EVERY_S = 20 * 60


def pc_sync(force: bool = False, fetch=None, key_path: str | None = None) -> dict:
    """The VAPID key + subscriptions the cloud shares with this PC (state.json on the private dashboard branch: push_pc.box
    sealed to the PC's heartbeat key, push_subs). Cached 20 min. fetch() -> state dict, for tests. Never raises."""
    if not force and fetch is None and _PC["sync"] is not None and time.time() - _PC["sync_t"] < SYNC_EVERY_S:
        return _PC["sync"]
    out = {"private": None, "subs": []}
    try:
        if fetch is not None:
            st = fetch()
        else:
            import subprocess
            r = subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", "dashboard"], cwd=ROOT, capture_output=True, text=True, timeout=60)
            if r.returncode:
                raise RuntimeError("no dashboard branch")
            r = subprocess.run(["git", "show", "FETCH_HEAD:state.json"], cwd=ROOT, capture_output=True, text=True, timeout=30)
            st = json.loads(r.stdout) if not r.returncode else {}
        box = ((st or {}).get("push_pc") or {}).get("box")
        mine = _read_json(key_path or PC_KEY_PATH).get("private")
        if box and mine:
            out["private"] = unseal(box, mine).decode()
        out["subs"] = [r["sub"] for r in (st or {}).get("push_subs") or [] if r.get("sub")]
        _PC["sync_err"] = None
    except Exception as e:
        _PC["sync_err"] = e.__class__.__name__
    _PC["sync"], _PC["sync_t"] = out, time.time()
    return out


def pc_config(sync=None) -> dict:
    s = sync if sync is not None else pc_sync()
    return config(private=s.get("private"), subs_extra=s.get("subs"))


def pc_notifier() -> Notifier:
    if _PC["notifier"] is None:
        _PC["notifier"] = Notifier(path=SENT_PATH, relay=Relay(timeout=4.0), src="pc")
    return _PC["notifier"]


def _pc_send(payload, push_it):
    try:
        n = pc_notifier()
        n.cfg = pc_config()
        if not enabled(n.cfg):
            n.mark(payload)
            n._save()
            return
        n.notify(payload, push_it=push_it)
    except Exception:
        pass


def pc_notify(payload: dict) -> dict | None:
    """PC side, in a background thread (git fetch / push service never delay order routing). Entry and outcome notices are
    pushed; other kinds only with LE_PUSH_EXTRA=1. Never raises."""
    try:
        if pc_notifier().seen(payload):
            return {"dup": True}
        # pc: update / auto-resume notices; ops: the owner's PC helpers (engine/ops_checks.py: pre-session, day / week
        # summary, internet / NinjaTrader drops, MFFU inactivity, eval passed / failed, contract roll)
        push_it = payload.get("kind") in ("fill", "outcome", "test", "pc", "ops") or extra_on()
        threading.Thread(target=_pc_send, args=(payload, push_it), name="push", daemon=True).start()
        return {"queued": True}
    except Exception:
        return None


def pc_send_now(payload: dict, sync=None, sender=None) -> dict:
    """PC side, synchronous, for a script or a scheduled task (no server thread to wait for): push one notice now. No
    de-duplication here (engine/ops_checks keeps its own keys in data/ops_state.json). sync = pc_sync() result, for
    tests. Never raises."""
    try:
        cfg = pc_config(sync)
        if not enabled(cfg):
            return {"sent": 0, "skipped": "not configured"}
        return send(payload, cfg=cfg, sender=sender)
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
