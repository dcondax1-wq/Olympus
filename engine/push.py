"""Web Push notifications to the phone app (the Home Screen web app at demetrades2000-coder.github.io/nq-dashboard).

Free and without a server of our own: the phone's browser (Apple / Google / Mozilla push service) delivers the message.
The app subscribes once from Settings (a tap on "Turn on notifications") and shows a code; that code goes into a GitHub
Secret, and the cloud monitor (tools/cloud_monitor.py) and the PC bot (engine/live.py, engine/ninjatrader.py) send to it.

Config, first found wins (nothing configured = every call is a silent no-op):
  LE_VAPID_PRIVATE      the VAPID private key: base64url of the raw 32-byte P-256 key (GitHub Secret, or data/push.json)
  LE_VAPID_PUBLIC       optional: the matching public key (it is derived from the private key when missing)
  LE_PUSH_SUBS          the app's subscription code(s): a JSON list, one object, or objects one after another
  LE_PUSH_SUBS_2 .. _5  more devices (a GitHub Secret cannot be read back, so each device can get its own secret)
  data/push.json        PC only (gitignored): {"vapid_private": "...", "subs": [...]} (Settings -> Alerts on the PC dashboard)
Keys: python tools/push_keys.py makes a pair (or the app makes one on the phone). The public key is not secret.

Sending uses pywebpush when it is installed, else the small built-in RFC 8291 (aes128gcm) + RFC 8292 (VAPID) sender
below, which needs only `cryptography`. Payloads are JSON {title, body, tag, url, kind, key, t, src} for tools/web_public/sw.js.
Never raises into the caller.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
import threading
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "data", "push.json")            # PC only, gitignored
SENT_PATH = os.path.join(ROOT, "data", "push_sent.json")         # PC de-dup keys, gitignored
APP_URL = "https://demetrades2000-coder.github.io/nq-dashboard/"
SUBJECT = os.environ.get("LE_PUSH_SUBJECT") or APP_URL            # VAPID "sub" claim: a contact URL (no e-mail needed)
TTL_S = 6 * 3600                                                  # a notice older than 6 h is not worth delivering
MAX_BODY = 600
POINT_VALUE = {"NQ": 2.0, "ES": 5.0}                              # $ per point of one micro (MNQ / MES)
_lock = threading.Lock()


# ---------------------------------------------------------------------------------------------- base64url helpers
def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64u_dec(s: str) -> bytes:
    s = str(s).strip()
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def endpoint_id(endpoint: str) -> str:
    """Short, non-reversible id of a subscription (the app compares it to its own to say 'this phone is connected')."""
    return hashlib.sha256(str(endpoint).encode()).hexdigest()[:12]


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
    """A new VAPID key pair: (private, public), both base64url."""
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    return b64u(k.private_numbers().private_value.to_bytes(32, "big")), b64u(_pub_bytes(k.public_key()))


# ---------------------------------------------------------------------------------------------- config
def parse_subs(text) -> list:
    """Subscriptions from a secret's text: a JSON list, one object, or several objects one after another (any spacing).
    Keeps only well-formed ones {endpoint: https://..., keys: {p256dh, auth}}, de-duplicated by endpoint."""
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
        if not (isinstance(ep, str) and ep.startswith("https://") and keys.get("p256dh") and keys.get("auth")):
            continue
        if ep in seen:
            continue
        seen.add(ep)
        out.append({"endpoint": ep, "keys": {"p256dh": keys["p256dh"], "auth": keys["auth"]}})
    return out


def _file_cfg(path=None) -> dict:
    try:
        with open(path or CONFIG_PATH, encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def config(env=None, path=None) -> dict:
    """{"private", "public", "subs", "source", "error"}; private None = not configured."""
    env = os.environ if env is None else env
    f = _file_cfg(path)
    priv = (env.get("LE_VAPID_PRIVATE") or "").strip() or (f.get("vapid_private") or "").strip() or None
    src = "env" if (env.get("LE_VAPID_PRIVATE") or "").strip() else "file" if priv else None
    texts = [env.get("LE_PUSH_SUBS")] + [env.get(f"LE_PUSH_SUBS_{i}") for i in range(2, 6)]
    subs = []
    for t in texts:
        subs += parse_subs(t)
    subs += parse_subs(f.get("subs"))
    subs = parse_subs(subs)
    pub, err = (env.get("LE_VAPID_PUBLIC") or "").strip() or (f.get("vapid_public") or "").strip() or None, None
    if priv:
        try:
            derived = public_from_private(priv)
            if pub and pub != derived:
                err = "LE_VAPID_PUBLIC does not match LE_VAPID_PRIVATE: using the one derived from the private key"
            pub = derived
        except Exception as e:
            err, priv = f"VAPID private key unusable ({e.__class__.__name__}: {e})", None
    return {"private": priv, "public": pub, "subs": subs, "source": src, "error": err}


def enabled(cfg=None) -> bool:
    c = cfg or config()
    return bool(c["private"] and c["subs"])


def status(cfg=None, last=None) -> dict:
    """Public view for the dashboards: never the private key or an endpoint, only short endpoint ids."""
    c = cfg or config()
    return {"configured": bool(c["private"]), "vapid_public": c["public"], "devices": len(c["subs"]),
            "device_ids": [endpoint_id(s["endpoint"]) for s in c["subs"]], "source": c["source"], "error": c["error"],
            "sender": sender_name(), **({"last": last} if last else {})}


# ---------------------------------------------------------------------------------------------- payloads
def _money(x) -> str:
    x = float(x or 0)
    return f"{'+' if x > 0 else '-' if x < 0 else ''}${abs(x):,.0f}"


def _px(x) -> str:
    return "-" if x is None else f"{float(x):,.2f}"


def _clip(s, n=MAX_BODY) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def _et_hm(t) -> str:
    try:
        import datetime as dt
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(int(t), ZoneInfo("America/New_York")).strftime("%H:%M")
    except Exception:
        return ""


EXIT_WORDS = {"TARGET": "target hit", "STOP": "stopped out", "BE": "breakeven", "TIME": "flat at the close (15:55)",
              "EOD": "flat at the close (15:55)", "TIME SAFETY": "flattened at the close (safety)", "KILL": "kill switch"}


def fill_payload(src: str, sym: str, side: str, qty, entry, stop, target, entry_t, setup: str = "", risk_pts=None,
                 note: str = "", model: str = "LIT", url: str | None = None, key: str | None = None) -> dict:
    """A fill: 'Cloud paper · LIT LONG filled' / '12 MNQ @ 21,034.25 · stop ... · target ... · $820 at risk'."""
    side = str(side or "").upper() or ("LONG" if (target or 0) > (entry or 0) else "SHORT")
    if risk_pts is None and entry is not None and stop is not None:
        risk_pts = abs(float(entry) - float(stop))
    pv = POINT_VALUE.get(str(sym).upper(), 2.0)
    risk_usd = float(qty or 0) * float(risk_pts or 0) * pv
    micro = "MNQ" if str(sym).upper() == "NQ" else "MES" if str(sym).upper() == "ES" else f"micro {sym}"
    lines = [f"{qty} {micro} @ {_px(entry)} · stop {_px(stop)} · target {_px(target)}",
             f"${risk_usd:,.0f} at risk ({float(risk_pts or 0):.1f} pt stop){' · ' + _et_hm(entry_t) + ' ET' if entry_t else ''}"]
    if setup:
        lines.append(setup)
    if note:
        lines.append(note)
    return {"kind": "fill", "src": src, "key": key or f"fill:{int(entry_t or 0)}", "t": int(entry_t or time.time()),
            "title": f"{src} · {model} {side} filled", "body": _clip("\n".join(lines)),
            "tag": f"{_tag(src)}-trade-{int(entry_t or 0)}", "url": url or f"#/activity/fill:{int(entry_t or 0)}",
            "side": side, "qty": qty, "entry": entry, "stop": stop, "target": target, "risk_usd": round(risk_usd, 2)}


def outcome_payload(src: str, sym: str, side: str, exit_reason: str, r, usd, entry_t, exit_t=None, qty=None,
                    balance=None, to_target=None, note: str = "", model: str = "LIT", url: str | None = None,
                    key: str | None = None) -> dict:
    """An outcome: 'Cloud paper · LIT LONG TARGET +3.20R +$2,560' / '... eval balance $52,560 ($440 to the target)'."""
    side = str(side or "").upper()
    reason = str(exit_reason or "EXIT").upper()
    rtxt = "" if r is None else f" {float(r):+.2f}R"
    lines = [f"{EXIT_WORDS.get(reason, reason.lower())}"
             + (f" · entry {_et_hm(entry_t)} → exit {_et_hm(exit_t)} ET" if entry_t and exit_t else "")
             + (f" · {qty} micros" if qty else "")]
    if balance is not None:
        lines.append(f"Eval balance ${float(balance):,.0f}"
                     + (f" (${max(0.0, float(to_target)):,.0f} to the $3k target)" if to_target is not None and float(to_target) > 0
                        else " (target reached)" if to_target is not None else ""))
    if note:
        lines.append(note)
    return {"kind": "outcome", "src": src, "key": key or f"out:{int(entry_t or 0)}", "t": int(exit_t or time.time()),
            "title": f"{src} · {model} {side} {reason}{rtxt} {_money(usd)}", "body": _clip("\n".join(lines)),
            "tag": f"{_tag(src)}-trade-{int(entry_t or 0)}", "url": url or f"#/activity/out:{int(entry_t or 0)}",
            "side": side, "exit": reason, "R": None if r is None else round(float(r), 2), "usd": round(float(usd or 0), 2)}


def text_payload(src: str, kind: str, title: str, body: str, key: str, t=None, url: str = "#/activity") -> dict:
    """Any other notice: PC heartbeat silent, eval timing flip, NinjaTrader risk, test."""
    return {"kind": kind, "src": src, "key": key, "t": int(t or time.time()), "title": _clip(f"{src} · {title}", 120),
            "body": _clip(body), "tag": f"{_tag(src)}-{kind}", "url": url}


def _tag(src) -> str:
    return "".join(c for c in str(src).lower() if c.isalnum()) or "le"


def wire(payload: dict) -> bytes:
    """What goes to the phone (under the 4 KB push limit): title, body, tag, url, kind, key, t, src."""
    keep = {k: payload.get(k) for k in ("title", "body", "tag", "url", "kind", "key", "t", "src")}
    b = json.dumps(keep, separators=(",", ":"), ensure_ascii=False).encode()
    if len(b) > 3000:
        keep["body"] = _clip(keep["body"], 300)
        b = json.dumps(keep, separators=(",", ":"), ensure_ascii=False).encode()
    return b


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
    prk_key = _hmac(auth_secret, shared)
    ikm = _hmac(prk_key, b"WebPush: info\x00" + ua_pub + as_pub + b"\x01")
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
    key = _priv_from_b64(priv_b64)
    r, s = decode_dss_signature(key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
    sig = b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={head}.{body}.{sig}, k={pub_b64 or public_from_private(priv_b64)}"


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
        resp = getattr(e, "response", None)
        return int(getattr(resp, "status_code", 0) or 0)


def sender_name() -> str:
    try:
        import pywebpush  # noqa: F401
        return "pywebpush"
    except Exception:
        return "built-in"


def _sender():
    return _send_pywebpush if sender_name() == "pywebpush" else _send_builtin


def send(payload: dict, cfg=None, sender=None) -> dict:
    """Send one notice to every subscription. {"sent": n, "devices": n, "gone": [ids], "errors": [...]}; never raises.
    gone = the push service answered 404/410: that device's subscription expired (turn notifications on again in the app
    and replace its secret)."""
    c = cfg or config()
    if not enabled(c):
        return {"sent": 0, "devices": len(c["subs"]), "skipped": "not configured"}
    send_one = sender or _sender()
    data = wire(payload)
    out = {"sent": 0, "devices": len(c["subs"]), "gone": [], "errors": []}
    for sub in c["subs"]:
        try:
            code = int(send_one(sub, data, c["private"], c["public"]))
        except Exception as e:
            out["errors"].append(f"{endpoint_id(sub['endpoint'])}: {e.__class__.__name__}: {str(e)[:120]}")
            continue
        if 200 <= code < 300:
            out["sent"] += 1
        elif code in (404, 410):
            out["gone"].append(endpoint_id(sub["endpoint"]))
        else:
            out["errors"].append(f"{endpoint_id(sub['endpoint'])}: HTTP {code}")
    return out


# ---------------------------------------------------------------------------------------------- de-duplication
class Notifier:
    """Sends each notice once, keyed by payload["key"] (prefixed with the source, so the PC's and the cloud's never collide
    and each says where it comes from). keys: an iterable of already-sent keys (the cloud keeps them in state.json); path: a
    JSON file that keeps them (the PC: data/push_sent.json). sender(sub, data, priv, pub) -> HTTP status, for tests."""

    def __init__(self, keys=None, path: str | None = None, sender=None, cfg=None, keep: int = 600):
        self.path, self.sender, self.cfg, self.keep = path, sender, cfg, keep
        self.sent: dict = {}
        if path:
            try:
                with open(path, encoding="utf-8") as fh:
                    self.sent = {str(k): float(v) for k, v in (json.load(fh) or {}).items()}
            except Exception:
                self.sent = {}
        for k in keys or []:
            self.sent.setdefault(str(k), time.time())
        self.log: list = []

    def full_key(self, payload: dict) -> str:
        return f"{_tag(payload.get('src') or '')}:{payload['key']}"

    def seen(self, payload: dict) -> bool:
        return self.full_key(payload) in self.sent

    def mark(self, payload: dict):
        self.sent[self.full_key(payload)] = time.time()

    def notify(self, payload: dict) -> dict:
        """Send unless already sent. The key is marked even when push is not configured, so a notice is never sent late
        (hours after the event) once the owner sets push up."""
        with _lock:
            k = self.full_key(payload)
            if k in self.sent:
                return {"dup": True, "key": k}
            self.sent[k] = time.time()
            if len(self.sent) > self.keep:
                for old in sorted(self.sent, key=self.sent.get)[: len(self.sent) - self.keep]:
                    self.sent.pop(old, None)
            self._save()
        try:
            res = send(payload, cfg=self.cfg, sender=self.sender)
        except Exception as e:                       # send() never raises; belt and braces for the trading loops
            res = {"sent": 0, "errors": [f"{e.__class__.__name__}: {e}"]}
        res["key"] = k
        self.log.append({"t": int(time.time()), "key": k, "title": payload.get("title"), **{x: res.get(x) for x in ("sent", "gone", "errors", "skipped")}})
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


_PC = None


def pc_notifier() -> Notifier:
    """The PC process's notifier (LiveBot and the NinjaTrader adapter share it): keys in data/push_sent.json."""
    global _PC
    if _PC is None:
        _PC = Notifier(path=SENT_PATH)
    return _PC


def pc_notify(payload: dict) -> dict | None:
    """PC side: send in a background thread so a slow push service never delays order routing. Never raises."""
    try:
        n = pc_notifier()
        if n.seen(payload):
            return {"dup": True}
        if not enabled():
            n.mark(payload)
            n._save()
            return {"skipped": "not configured"}
        threading.Thread(target=n.notify, args=(payload,), name="push", daemon=True).start()
        return {"queued": True}
    except Exception:
        return None


# ---------------------------------------------------------------------------------------------- PC config (data/push.json)
def save_pc_config(patch: dict, path: str | None = None) -> dict:
    """Settings -> Alerts on the PC dashboard: store the private key and/or subscriptions in data/push.json (gitignored).
    subs_mode 'add' (default) appends to the stored ones, 'replace' replaces them."""
    path = path or CONFIG_PATH
    cur = _file_cfg(path)
    priv = (patch.get("vapid_private") or "").strip()
    if priv:
        public_from_private(priv)                    # raises ValueError on a bad key: the API returns the message
        cur["vapid_private"] = priv
        cur.pop("vapid_public", None)
    if patch.get("subs") is not None:
        new = parse_subs(patch.get("subs"))
        if patch.get("subs") and not new:
            raise ValueError("no subscription found in that text: copy the whole code from the app")
        cur["subs"] = new if patch.get("subs_mode") == "replace" else parse_subs((cur.get("subs") or []) + new)
    if patch.get("clear"):
        cur = {}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cur, fh, indent=1)
    return status(config(path=path))
