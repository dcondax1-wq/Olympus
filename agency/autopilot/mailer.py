"""EMAIL AUTOPILOT transport: Gmail SMTP (send) and IMAP (read replies), stdlib only. The app password is used here and nowhere else;
it is never logged, printed or written anywhere but the owner's own %USERPROFILE%\\.olympus\\agency_mail.json. Tests pass fake factories."""
from __future__ import annotations

import email
import email.policy
import email.utils
import imaplib
import smtplib
import ssl
from email.message import EmailMessage


def build(cfg: dict, to: str, subject: str, body: str, reply_to_id: str = "") -> EmailMessage:
    m = EmailMessage()
    m["From"] = email.utils.formataddr((f"{cfg.get('from_name')} ({cfg.get('business_name')})", cfg["from_address"]))
    m["To"] = to
    m["Subject"] = subject
    m["Date"] = email.utils.formatdate(localtime=False)
    m["Message-ID"] = email.utils.make_msgid(domain=cfg["from_address"].split("@")[-1])
    # one-click "no thanks" for mail apps (Gmail / Apple Mail show an Unsubscribe link): a reply to us, handled like an opt-out
    m["List-Unsubscribe"] = f"<mailto:{cfg['from_address']}?subject=unsubscribe>"
    if reply_to_id:
        m["In-Reply-To"] = reply_to_id
        m["References"] = reply_to_id
    m.set_content(body)
    return m


class Smtp:
    """one login per run; send() returns the Message-ID. factory = a fake smtplib.SMTP_SSL for the tests"""

    def __init__(self, cfg: dict, factory=None):
        self.cfg, self.factory, self.s = cfg, factory, None

    def __enter__(self):
        f = self.factory or (lambda h, p: smtplib.SMTP_SSL(h, p, context=ssl.create_default_context(), timeout=30))
        self.s = f(self.cfg["smtp_host"], int(self.cfg["smtp_port"]))
        self.s.login(self.cfg["from_address"], self.cfg["app_password"])
        return self

    def send(self, to: str, subject: str, body: str, reply_to_id: str = "") -> str:
        m = build(self.cfg, to, subject, body, reply_to_id)
        self.s.send_message(m)
        return m["Message-ID"]

    def __exit__(self, *a):
        try:
            self.s.quit()
        except Exception:  # noqa: BLE001
            pass


def plain_text(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                try:
                    return part.get_content()
                except Exception:  # noqa: BLE001
                    return (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
        return ""
    try:
        return msg.get_content() if msg.get_content_type() == "text/plain" else ""
    except Exception:  # noqa: BLE001
        return (msg.get_payload(decode=True) or b"").decode("utf-8", "replace")


def fetch_new(cfg: dict, last_uid: int, limit: int = 50, factory=None) -> list:
    """[{uid, from, subject, text, message_id, in_reply_to}] newer than last_uid in the INBOX (read-only: nothing is marked or moved)"""
    f = factory or (lambda h: imaplib.IMAP4_SSL(h, ssl_context=ssl.create_default_context(), timeout=30))
    M = f(cfg["imap_host"])
    out = []
    try:
        M.login(cfg["from_address"], cfg["app_password"])
        M.select("INBOX", readonly=True)
        typ, data = M.uid("search", None, f"UID {int(last_uid) + 1}:*")
        uids = [int(x) for x in (data[0].split() if data and data[0] else []) if int(x) > int(last_uid)][:limit]
        for u in uids:
            typ, d = M.uid("fetch", str(u), "(RFC822)")
            raw = next((x[1] for x in d if isinstance(x, tuple)), b"")
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            out.append({"uid": u, "from": email.utils.parseaddr(str(msg.get("From", "")))[1].lower(), "from_name": str(msg.get("From", "")),
                        "subject": str(msg.get("Subject", "")), "text": plain_text(msg), "message_id": str(msg.get("Message-ID", "")),
                        "in_reply_to": str(msg.get("In-Reply-To", ""))})
    finally:
        try:
            M.logout()
        except Exception:  # noqa: BLE001
            pass
    return out
