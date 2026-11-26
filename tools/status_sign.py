#!/usr/bin/env python3
"""STATUS SIGN (day-security 2026-11-20): proof that a post on the PUBLIC ntfy status topic came from the owner's PC.

Why: the status topic's name is public (tools/web_public/status_feed.json), and ntfy.sh lets ANYONE post to a topic. Before this,
one forged post with a time in the future showed fake balances on every page, replaced the PC's push keys ("wp") and put a fake
"owner note" / "Decide ...: YES" in front of every Claude session (tools/board.py read). Free, no account, no paid service:

  * the PC keeps an ECDSA P-256 private key (never in the repo; default <home>/.olympus/status_sign.json, like ntfy.json);
  * every status / ext post ends with  ,"sg":"<86 chars>"}  = a signature of the exact text before it (no re-encoding, so the
    phone's WebCrypto and Python check the same bytes); older readers just see one more key and ignore it;
  * the public verify key ("vk", 87 chars, not a secret) sits in tools/web_public/status_feed.json; once it is there the site
    (tools/web_public/pc_feed.js) and Claude's board (tools/board.py) ignore every unsigned or badly signed post.

Before a "vk" is pinned nothing changes, except that a post dated in the future (more than SKEW_S ahead) is never believed.

  python tools/status_sign.py keygen [--out PATH]    on the PC, once: makes the key file (refuses to overwrite), prints ONLY the vk
  python tools/status_sign.py vk [--key PATH]        prints the public verify key of an existing key file
  python tools/status_sign.py check                  reads the live topic: how many posts verify against the pinned vk (read only)

Pure helpers (tests: python -X utf8 -m tests.test_status_sign):
  sign_text(text, priv)  -> text with the "sg" field added          verify_text(text, vk) -> bool
  split(text)            -> (original text, sig) or None            filter_msgs(msgs, vk, now) -> the ntfy messages to believe
Needs `cryptography` for signing and Python verification (the PC and the cloud have it); without it verify_text says False.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_FEED = os.path.join(ROOT, "tools", "web_public", "status_feed.json")
DEFAULT_KEY = os.path.join(os.path.expanduser("~"), ".olympus", "status_sign.json")
CONTEXT = b"le-status-v1\n"                   # signed = CONTEXT + text: a signature made for anything else never fits here
SIG_FIELD = ',"sg":"'
SIG_RX = re.compile(r"^[A-Za-z0-9_-]{86}$")   # 64 bytes (r || s), base64url without padding
VK_RX = re.compile(r"^[A-Za-z0-9_-]{87}$")    # 65 bytes (0x04 || x || y), base64url without padding
SKEW_S = 600                                  # a post more than 10 minutes in the future is forged (or a broken clock)


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")


def unb64u(s: str) -> bytes:
    s = str(s or "")
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ------------------------------------------------------------------------------------------------ keys
def keygen() -> tuple:
    """(private PKCS8 DER base64, public vk). The private part goes only into the PC's key file."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    priv = k.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    return base64.b64encode(priv).decode("ascii"), vk_of(k)


def _load_priv(priv):
    from cryptography.hazmat.primitives import serialization
    if hasattr(priv, "sign"):
        return priv
    return serialization.load_der_private_key(base64.b64decode(str(priv)), password=None)


def vk_of(priv) -> str:
    from cryptography.hazmat.primitives import serialization
    k = _load_priv(priv)
    return b64u(k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))


def load_key(path: str | None = None) -> str | None:
    """The PC's private key (base64) from its key file, or None. LE_STATUS_SIGN_KEY = another file (tests)."""
    p = path or os.environ.get("LE_STATUS_SIGN_KEY") or DEFAULT_KEY
    try:
        with open(p, encoding="utf-8") as fh:
            v = (json.load(fh) or {}).get("private")
        return str(v) if v else None
    except (OSError, ValueError, AttributeError):
        return None


def ensure_key(path: str | None = None, env=None, say=print) -> str | None:
    """The PC's key file, made once if missing: Windows PC only (os.name nt) or LE_STATUS_SIGN_KEYGEN=1, never in the cloud
    (LE_CLOUD / GITHUB_ACTIONS). O_EXCL + 0600, so two runs at once never make two keys. -> the public vk, or None. Never raises."""
    env = os.environ if env is None else env
    try:
        p = path or env.get("LE_STATUS_SIGN_KEY") or DEFAULT_KEY
        k = load_key(p)
        if k:
            return vk_of(k)
        if env.get("LE_CLOUD") or env.get("GITHUB_ACTIONS") or not (os.name == "nt" or env.get("LE_STATUS_SIGN_KEYGEN") == "1"):
            return None
        priv, vk = keygen()
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            k = load_key(p)
            return vk_of(k) if k else None
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"kind": "le-status-sign", "private": priv, "vk": vk, "made": int(time.time())}, fh)
        say(f"[status_sign] made this PC's status key (private part stays here). Public key starts {vk[:6]}")
        return vk
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------------------------------------ sign / verify
def sign_text(text, priv) -> str:
    """The exact text with ,"sg":"..."} at the end. text: a JSON object as a string (or a dict, encoded compactly here)."""
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    if isinstance(text, dict):
        text = json.dumps(text, separators=(",", ":"), ensure_ascii=False)
    text = str(text)
    if not (text.startswith("{") and text.endswith("}")) or len(text) < 3:
        raise ValueError("sign_text needs a non-empty JSON object")
    der = _load_priv(priv).sign(CONTEXT + text.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return text[:-1] + SIG_FIELD + b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big")) + '"}'


def split(text):
    """(original text, sig) of a signed text, else None."""
    t = str(text or "")
    if not t.endswith('"}'):
        return None
    i = t.rfind(SIG_FIELD)
    if i <= 0:
        return None
    sig = t[i + len(SIG_FIELD):-2]
    if not SIG_RX.match(sig):
        return None
    return t[:i] + "}", sig


def verify_text(text, vk) -> bool:
    """True only when the text carries a valid signature by the key vk. Never raises."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        if not VK_RX.match(str(vk or "")):
            return False
        sp = split(text)
        if not sp:
            return False
        orig, sig = sp
        raw = unb64u(sig)
        der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
        pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64u(vk))
        try:
            pub.verify(der, CONTEXT + orig.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
            return True
        except InvalidSignature:
            return False
    except Exception:  # noqa: BLE001
        return False


def _times(m: dict) -> list:
    out = []
    try:
        j = json.loads(m.get("message") or "")
    except (ValueError, TypeError):
        j = None
    if isinstance(j, dict):
        rep = j.get("reporter") if isinstance(j.get("reporter"), dict) else {}
        brd = j.get("brd") if isinstance(j.get("brd"), dict) else {}
        for v in (j.get("t"), j.get("rt"), rep.get("t"), brd.get("t")):
            try:
                out.append(float(v))
            except (TypeError, ValueError):
                pass
    return out


def future(m: dict, now: float | None = None, skew: float = SKEW_S) -> bool:
    """A message whose own times (t, rt, reporter.t, brd.t) lie more than skew seconds ahead: never believed."""
    now = time.time() if now is None else float(now)
    return any(t > now + skew for t in _times(m))


ROTATE_KIND = "le-key-rotate"


def rotation_text(old_priv, new_vk: str, now: float | None = None) -> str:
    """The PC's planned key change, signed by the OLD key: {"v":1,"kind":"le-key-rotate","t","old","new"} + sg. A reader that
    trusts `old` then trusts `new` too (accepted()); nobody else can make one."""
    t = int(time.time() if now is None else now)
    body = json.dumps({"v": 1, "kind": ROTATE_KIND, "t": t, "old": vk_of(old_priv), "new": new_vk}, separators=(",", ":"))
    return sign_text(body, old_priv)


def accepted(msgs, vks) -> list:
    """The keys to believe: the pinned ones + every key a trusted key handed over in a signed rotation post (chained, oldest
    first). Pure apart from the signature checks."""
    keys = [k for k in ([vks] if isinstance(vks, str) else list(vks or [])) if k and VK_RX.match(str(k))]
    rots = []
    for m in msgs or []:
        try:
            j = json.loads((m or {}).get("message") or "")
        except (ValueError, TypeError, AttributeError):
            continue
        if isinstance(j, dict) and j.get("kind") == ROTATE_KIND and VK_RX.match(str(j.get("new") or "")):
            rots.append((float(j.get("t") or 0), m.get("message"), str(j.get("old") or ""), str(j["new"])))
    changed = True
    while changed:
        changed = False
        for _t, txt, old, new in sorted(rots):
            if new not in keys and old in keys and verify_text(txt, old):
                keys.append(new)
                changed = True
    return keys


def filter_msgs(msgs, vk=None, now: float | None = None) -> list:
    """The ntfy messages a reader may believe: never one dated in the future; with pinned key(s) (a vk string or a list), only
    those signed by a pinned key or by a key a pinned key rotated to (accepted()).
    Messages that are not JSON objects pass the vk check only when unsigned text is not a status post (left to the caller)."""
    keys = accepted(msgs, vk) if vk else []
    out = []
    for m in msgs or []:
        if not isinstance(m, dict) or future(m, now):
            continue
        if keys and not any(verify_text(m.get("message"), k) for k in keys):
            continue
        out.append(m)
    return out


def svk_counts(msgs) -> dict:
    """Pinning once (trust on first use): {vk: {"n", "first", "last"}} of the posts that carry "svk" (the PC's public key) AND
    verify under it. The PC's key signs every post every 15 minutes for hours; a forger's key shows few posts in a short span."""
    out = {}
    for m in msgs or []:
        try:
            j = json.loads((m or {}).get("message") or "")
        except (ValueError, TypeError, AttributeError):
            continue
        vk = str(j.get("svk") or "") if isinstance(j, dict) else ""
        if not vk or not verify_text(m.get("message"), vk):
            continue
        t = float(m.get("time") or 0)
        r = out.setdefault(vk, {"n": 0, "first": t, "last": t})
        r["n"] += 1
        r["first"], r["last"] = min(r["first"], t), max(r["last"], t)
    return out


def feed_vks(path: str | None = None) -> list:
    """Every pinned key of status_feed.json: "vk" first, then the "vks" list (a new PC key pinned beside the old one: no lock-out
    while both run). [] = not pinned yet."""
    try:
        first = feed_vk(path)                       # (tests replace feed_vk: the "vk" always comes through it)
        try:
            with open(path or STATUS_FEED, encoding="utf-8") as fh:
                d = json.load(fh) or {}
        except (OSError, ValueError):
            d = {}
        ks = ([first] if first else []) + [str(x) for x in (d.get("vks") or []) if isinstance(x, str)]
        out = []
        for k in ks:
            if VK_RX.match(k) and k not in out:
                out.append(k)
        return out
    except (OSError, ValueError, AttributeError):
        return []


def candidate(msgs, keys, now: float | None = None, quiet_s: float = 3 * 3600, min_n: int = 12, min_span_s: float = 3 * 3600):
    """The 3-hour window (lock-out guard): when NO trusted key signed anything for quiet_s but ONE other key signed min_n+ posts
    (carrying its own svk) over min_span_s, that key is probably the PC's new one (a reinstall / new Windows profile / new PC).
    -> {"vk", "n", "first", "last"} or None. Never trusted by itself: the board says so, the phone asks the owner."""
    now = time.time() if now is None else float(now)
    keys = list(keys or [])
    last_ok = max((float(m.get("time") or 0) for m in msgs or [] if isinstance(m, dict)
                   and any(verify_text(m.get("message"), k) for k in keys)), default=0.0)
    if keys and now - last_ok < quiet_s:
        return None
    best = None
    for k, r in svk_counts(msgs).items():
        if k in keys or r["n"] < min_n or r["last"] - r["first"] < min_span_s:
            continue
        if best is None or r["n"] > best["n"]:
            best = {"vk": k, **r}
    return best


def pin(vk: str, path: str | None = None, replace: bool = False) -> list:
    """Add vk to status_feed.json ("vk" when none, else "vks"; replace=True makes it the only key). -> the pinned keys."""
    p = path or STATUS_FEED
    if not VK_RX.match(str(vk or "")):
        raise ValueError("not a verify key (87 characters)")
    with open(p, encoding="utf-8") as fh:
        d = json.load(fh) or {}
    if replace or not VK_RX.match(str(d.get("vk") or "")):
        d["vk"], d["vks"] = vk, []
    elif vk != d.get("vk") and vk not in (d.get("vks") or []):
        d["vks"] = list(d.get("vks") or []) + [vk]
    if not d.get("vks"):
        d.pop("vks", None)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1)
        fh.write("\n")
    os.replace(tmp, p)
    return feed_vks(p)


def feed_vk(path: str | None = None) -> str | None:
    """The pinned public verify key of status_feed.json, or None (not pinned yet)."""
    try:
        with open(path or STATUS_FEED, encoding="utf-8") as fh:
            v = str((json.load(fh) or {}).get("vk") or "")
        return v if VK_RX.match(v) else None
    except (OSError, ValueError, AttributeError):
        return None


# ------------------------------------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("keygen")
    g.add_argument("--out", default=None)
    v = sub.add_parser("vk")
    v.add_argument("--key", default=None)
    sub.add_parser("check")
    r = sub.add_parser("rotate")
    r.add_argument("--key", default=None)
    pn = sub.add_parser("pin")
    pn.add_argument("prefix", help="the first characters of the key (from check / the board) or the whole key")
    pn.add_argument("--replace", action="store_true", help="make it the ONLY pinned key (default: pinned beside the old one)")
    a = ap.parse_args(argv)
    if a.cmd == "rotate":
        return rotate(a.key)
    if a.cmd == "pin":
        return pin_cli(a.prefix, a.replace)
    if a.cmd == "keygen":
        out = a.out or DEFAULT_KEY
        if os.path.exists(out):
            print(f"[KEEP] a key file already exists ({out}): its vk is {vk_of(load_key(out))}")
            return 0
        priv, vk = keygen()
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"kind": "le-status-sign", "private": priv, "vk": vk, "made": int(time.time())}, fh)
        print(f"[OK] key file made (private part stays on this PC). Public verify key, safe to share:\n{vk}")
        return 0
    if a.cmd == "vk":
        k = load_key(a.key)
        if not k:
            print("[FIX] no key file: python tools/status_sign.py keygen")
            return 1
        print(vk_of(k))
        return 0
    from tools import pc_silent_check as P
    with open(STATUS_FEED, encoding="utf-8") as fh:
        feed = json.load(fh)
    ok, msgs = P.poll(str(feed.get("ntfy") or "https://ntfy.sh").rstrip("/"), str(feed.get("topic") or ""), since="12h")
    vks = feed_vks()
    vk = vks[0] if vks else None
    keys = accepted(msgs, vks) if vks else []
    good = sum(1 for m in msgs if any(verify_text(m.get("message"), k) for k in keys))
    fut = sum(1 for m in msgs if future(m))
    print(f"status topic answered: {ok}; posts {len(msgs)}; future-dated (ignored) {fut}; "
          + (f"signed by the pinned key {good}" if vk else "no vk pinned yet (status_feed.json)"))
    for k, r in sorted(svk_counts(msgs).items(), key=lambda kv: -kv[1]["n"]):
        span = (r["last"] - r["first"]) / 3600.0
        print(f"  key {k[:6]}... signed {r['n']} posts over {span:.1f} h" + ("  <- pinned" if k in vks else "  <- rotated to by a pinned key" if k in keys else
              ("  (pin only a key with ~4 posts an hour for 6 h+, and the same first 6 characters the PC printed)")))
    c = candidate(msgs, keys) if vks else None
    if c:
        print(f"  [!!] NO pinned key signed anything for 3 h+, but key {c['vk'][:6]}... signed {c['n']} posts over "
              f"{(c['last'] - c['first']) / 3600:.1f} h: if the owner reinstalled / changed the PC, pin it: "
              f"python tools/status_sign.py pin {c['vk'][:12]}")
    return 0


ROTATE_REPOST_S, ROTATE_KEEP_S = 6 * 3600, 14 * 86400


def rotate(key_path: str | None = None, post=None, now: float | None = None) -> int:
    """On the PC: a NEW key, handed over by a post signed with the OLD one (every reader that trusts the old key trusts the new
    one at once: accepted()). The old key file is kept beside it (status_sign.old-<t>.json); the hand-over post is repeated by the
    15-minute report every 6 h for 14 days (ntfy keeps a post 12 h). Then Claude pins the new key (pin). Never on a non-PC."""
    p = key_path or os.environ.get("LE_STATUS_SIGN_KEY") or DEFAULT_KEY
    old = load_key(p)
    if not old:
        print("[FIX] no key file here: nothing to rotate (python tools/status_sign.py keygen makes the first one)")
        return 1
    t = int(time.time() if now is None else now)
    priv, vk = keygen()
    text = rotation_text(old, vk, now=t)
    if post is None:
        from tools import pc_report as R
        with open(STATUS_FEED, encoding="utf-8") as fh:
            feed = json.load(fh) or {}
        post = lambda body: R.ntfy_post(str(feed.get("ntfy") or "https://ntfy.sh"), str(feed.get("topic") or ""), body,  # noqa: E731
                                        priority="min")
    ok, why = post(text)
    if not ok:
        print(f"[FIX] the hand-over post did not go out ({why}): the old key stays, nothing changed")
        return 1
    try:
        with open(p, encoding="utf-8") as fh:
            rec_old = json.load(fh) or {}
        bak = os.path.join(os.path.dirname(p), f"status_sign.old-{t}.json")
        fd = os.open(bak, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(rec_old, fh)
        tmp = p + ".new"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump({"kind": "le-status-sign", "private": priv, "vk": vk, "made": t,
                       "rotation": {"text": text, "t": t, "posted": t}}, fh)
        os.replace(tmp, p)
    except OSError as e:
        print(f"[FIX] the new key could not be saved ({e.__class__.__name__}): the old key stays (the hand-over post names a key "
              "nobody holds: harmless)")
        return 1
    print(f"[OK] new status key (the old one signed the hand-over; it is kept in {os.path.basename(bak)}). New public key:\n{vk}\n"
          f"Claude: python tools/status_sign.py pin {vk[:12]}  (then commit tools/web_public/status_feed.json)")
    return 0


def rotation_pending(key_path: str | None = None, now: float | None = None) -> bool:
    """A rotate made in the last 14 days (the hand-over post carries the new key to every reader that trusts the old one)."""
    p = key_path or os.environ.get("LE_STATUS_SIGN_KEY") or DEFAULT_KEY
    try:
        with open(p, encoding="utf-8") as fh:
            r = (json.load(fh) or {}).get("rotation") or {}
        return bool(r.get("text")) and (time.time() if now is None else float(now)) - float(r.get("t") or 0) <= ROTATE_KEEP_S
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def rotation_due(key_path: str | None = None, now: float | None = None) -> str | None:
    """The hand-over post text when it should be repeated now (every 6 h for 14 days after a rotate), else None. Marks it posted."""
    p = key_path or os.environ.get("LE_STATUS_SIGN_KEY") or DEFAULT_KEY
    now = time.time() if now is None else float(now)
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh) or {}
        r = d.get("rotation") or {}
        if not r.get("text") or now - float(r.get("t") or 0) > ROTATE_KEEP_S or now - float(r.get("posted") or 0) < ROTATE_REPOST_S:
            return None
        r["posted"] = int(now)
        d["rotation"] = r
        tmp = p + ".new"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        os.replace(tmp, p)
        return str(r["text"])
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def pin_cli(prefix: str, replace: bool = False) -> int:
    """Claude, in the cloud: pin the key that starts with `prefix` (read from the live topic), beside the old one."""
    if VK_RX.match(prefix or ""):
        vk = prefix
    else:
        from tools import pc_silent_check as P
        with open(STATUS_FEED, encoding="utf-8") as fh:
            feed = json.load(fh)
        ok, msgs = P.poll(str(feed.get("ntfy") or "https://ntfy.sh").rstrip("/"), str(feed.get("topic") or ""), since="12h")
        hits = [k for k in svk_counts(msgs) if k.startswith(prefix or "-")]
        if len(hits) != 1:
            print(f"[FIX] {len(hits)} keys on the topic start with {prefix!r}: give more characters (python tools/status_sign.py check)")
            return 1
        vk = hits[0]
    keys = pin(vk, replace=replace)
    print(f"[OK] pinned {vk[:12]}... ({len(keys)} key(s) now). Commit tools/web_public/status_feed.json and publish the site.")
    return 0


if __name__ == "__main__":
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    sys.exit(main())
