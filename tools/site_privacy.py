#!/usr/bin/env python3
"""SITE PRIVACY (team Q2 "privacy and security audit", 2026-11-14): the ONE place that says what may never be in the PUBLIC site
(tools/build_web_dashboard.py -> the folder / zip the owner puts on Netlify, tools/pc_publish.py) or in the PUBLIC ntfy status topic
(tools/pc_report.lite). docs/PRIVACY.md is the plain-words table. Stdlib only; nothing here raises into a build or a report.

  scan(site)            every finding in a built site folder: card numbers (Luhn), bank / card account numbers, emails, phone numbers,
                        street addresses, an age / birthday, the owner's own name / email / broker account names (canaries), API keys and
                        tokens, the private ntfy alert topic, broker account ids, personal folders (C:\\Users\\<name>), tailnet names,
                        private files (household, day, inbox, health, cards, agency, calendars, keys) by name or by content.
                        -> [Finding]; a value is never printed whole (masked()).
  scrub(site)           the build's last step (and pc_publish's, after it adds kalshi.json): broker account ids keep only their last
                        4 digits ("MFFUEVBLDR...6789"), a personal folder becomes <you>, an email j***@domain, a card number ...1111,
                        an age ("before I turn 19") goes, a commit author ("who" next to a "sha") is dropped, a private file that should never be there is removed. Data
                        files only (.json .md .txt .csv; never code or a licence); JSON stays valid; a file without a hit is untouched.
  public_status(obj)    the same masking for the dict posted to the PUBLIC ntfy status topic, plus no PC name / login / broker fields.
  canaries(state)       the values only this PC knows (git authors, the heartbeat's broker account names, the ntfy alert topic),
                        collected at run time: nothing private is written in this file.

  python tools/site_privacy.py --scan <site> [--state state.json]    the findings (masked); exit 1 when there is one
  python tools/site_privacy.py --scrub <site> [--state state.json]   scrub in place, print what changed
Test: python -X utf8 -m tests.test_public_build_privacy
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------------------------------------------------------------------ files that are private
# names written only on the PC's private side: money_out/household.json + agency.json (tools/money_import.py, agency/billing),
# data/day/day.json + inbox.json (tools/calendar_sync.py, engine/day_inbox.py), <home>\.olympus\ (ntfy.json, netlify.json,
# publish.json, calendars.json, money\ledger.json, balances.json, oikos_ledger.json), data/agency/ (business, invoices, clients /
# crm / leads), the gitignored PC files (alerts with keys, tv.json, autostart.json, live_state.json, push*.json, memory.db)
PRIVATE_NAMES = {"household.json", "agency.json", "day.json", "inbox.json", "calendars.json", "ntfy.json", "netlify.json", "publish.json",
                 "balances.json", "money_ledger.json", "oikos_ledger.json", "networth.json", "net_worth.json", "business.json",
                 "invoices.json", "clients.json", "crm.json", "leads.json", "tv.json", "tv_device.json", "autostart.json", "live_state.json",
                 "push.json", "push_pc_key.json", "push_sent.json", "memory.db", "goals_money.json", "money_rules.json", "fleet.json",
                 "health.json", "cards.json", "card_tracker.json", "heartbeat_last.json", "heartbeat.json", ".env"}
DATA_EXT = (".json", ".jsonl", ".csv", ".txt", ".md")
PRIVATE_PREFIXES = ("household", "health_", "cards_", "card_tracker", "bank_", "statement_")      # data files only
PRIVATE_SUFFIXES = (".ics", ".ofx", ".qfx", ".qbo", ".pem", ".key", ".p12", ".pfx", ".env", ".jsonl", ".db", ".sqlite", ".kdbx")
# "kind" markers of the private writers (money_import, calendar_sync, day_inbox, agency/billing; the health / cards inbox of team ME1)
PRIVATE_KINDS = {"olympus-household", "olympus-money-ledger", "olympus-day", "olympus-inbox", "olympus-health", "olympus-cards",
                 "olympus-card-tracker", "olympus-agency", "olympus-agency-summary", "agency-summary", "olympus-calendars"}
SECRET_KEYS = {"telegram_token", "telegram_chat", "discord_webhook", "vapid_private", "private_key", "netlify_token", "api_key", "apikey",
               "api_secret", "client_secret", "password", "passwd", "kalshi_key", "kalshi_key_id", "kalshi_private_key", "tradovate_password",
               "access_token", "refresh_token", "auth_token", "webhook_key", "push_subs"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".glb", ".bin", ".mp3", ".ogg", ".wav", ".mp4", ".webm", ".woff", ".woff2",
              ".ttf", ".otf", ".wasm", ".gz", ".zip", ".hdr", ".exr", ".ktx2", ".basis", ".pdf", ".avif", ".m4a", ".flac"}
TEXT_SCRUB_EXT = {".json", ".md", ".txt", ".csv", ".webmanifest"}      # what scrub() may rewrite: data, never code (.js .html .css .py)

# ------------------------------------------------------------------------------------------------ detectors
CARD_RX = re.compile(r"(?<![\w.$/#=@+-])([2-6]\d{3}(?:[ -]?\d{4}){2}[ -]?\d{1,7}|3[47]\d{2}[ -]?\d{6}[ -]?\d{5})(?![\w])")
LONGNUM_RX = re.compile(r"(?<![\w.])\d{8,17}(?![\w.])")
ACCT_WORD_RX = re.compile(r"(account|acct|a/c|routing|aba|iban|checking|savings|member|card)\s*(no\.?|number|num|#|nr)?\s*[:#=]?\s*[\"']?\s*$")
EMAIL_RX = re.compile(r"([A-Za-z0-9][A-Za-z0-9._%+-]{0,63})@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24})(?![\w-])")
PHONE_RX = re.compile(r"(?<![\w.:/-])(?:\+?1[ .-])?(?:\(([2-9]\d{2})\)\s?|([2-9]\d{2})[ .-])([2-9]\d{2})[ .-](\d{4})(?![\w.:-])")
STREET_RX = re.compile(r"\b(\d{1,6})\s+(?:[NSEW]\.?\s+)?((?:[A-Z][a-z]+\s+){1,3})(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|"
                       r"Court|Ct|Terrace|Ter|Circle|Cir|Parkway|Pkwy|Highway|Hwy|Place|Pl|Way)\b\.?(?:,?\s+(?:Apt|Suite|Ste|Unit|#)\s*\w+)?")
ZIP_HINT_RX = re.compile(r"\b[A-Z]{2},?\s+\d{5}\b")
STATE_ZIP_RX = re.compile(r"\b(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|"
                          r"OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC),?\s+(\d{5})(?:-\d{4})?\b")
TOKEN_RX = [  # (name, a literal every match contains (cheap pre-check), pattern): a match is a secret in any file
    ("private key", "PRIVATE KEY", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED |PGP )?PRIVATE KEY(?: BLOCK)?-----")),
    ("AWS key", "IA", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GitHub token", "_", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("Slack token", "xox", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("Stripe secret", "_live_", re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b")),
    ("OpenAI / Anthropic key", "sk-", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{24,}\b")),
    ("Google API key", "AIza", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Telegram bot token", ":AA", re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}\b")),
    ("Discord webhook", "/api/webhooks/", re.compile(r"discord(?:app)?\.com/api/webhooks/\d+/[\w-]{20,}")),
    ("Netlify token", "nfp_", re.compile(r"\bnfp_[A-Za-z0-9]{30,}\b")),
    ("ntfy access token", "tk_", re.compile(r"\btk_[a-z0-9]{29}\b")),
    ("JWT", "eyJ", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{16,}")),
    ("push subscription", "https://", re.compile(r"https://(?:fcm\.googleapis\.com/fcm/send|updates\.push\.services\.mozilla\.com/wpush|"
                                                 r"web\.push\.apple\.com|[a-z0-9-]+\.notify\.windows\.com/w)/[A-Za-z0-9_:%-]{20,}")),
]
KEY_WORDS = ("password", "passwd", "secret", "api_key", "apikey", "api-key", "api_secret", "access_token", "accesstoken", "auth_token",
             "authtoken", "refresh_token", "private_key", "privatekey", "vapid_private", "telegram_token", "webhook_key", "netlify_token",
             "kalshi_key", "kalshi-key")
KEY_ASSIGN_RX = re.compile(r"(?i)[\"']?\b(?:password|passwd|secret|client_secret|api[_-]?key|api[_-]?secret|access[_-]?token|auth[_-]?token|"
                           r"refresh[_-]?token|private[_-]?key|vapid_private|telegram_token|webhook_key|netlify_token|kalshi[_-]?key(?:_id)?)\b[\"']?"
                           r"\s*[:=]\s*[\"']([A-Za-z0-9+/=_.~-]{16,})[\"']")
NTFY_WORDS = ("amber anchor apple arrow aspen atlas autumn badger bamboo banjo basil beacon birch bison blaze breeze brook cactus camel canyon cedar "
              "cobalt comet coral cotton crane crystal dahlia delta desert dolphin dove eagle ember falcon fern fjord flint forest fox galaxy garnet "
              "glacier granite harbor hazel heron hickory honey indigo iris island ivory jade jasmine juniper kayak kestrel lagoon lantern lemon lily "
              "lotus lynx maple marble meadow mesa meteor mint moose nectar nova oak ocean olive onyx orchid otter panda pearl pepper pine planet "
              "plum polar poppy prairie quartz rain raven reef ridge river robin ruby saffron sage salmon sapphire sequoia shadow sierra silver "
              "sparrow spruce storm summit sunset swan thunder tiger topaz tulip tundra velvet violet walnut willow winter wolf zephyr").split()
# tools/pc_report.make_topic's private alert topic: nq-<word>-<word>-<word>-<4 digits> (the docstring's own example is allowed)
NTFY_TOPIC_RX = re.compile(r"\bnq-(?:%s)-(?:%s)-(?:%s)-\d{4}\b" % (("|".join(NTFY_WORDS),) * 3))
NTFY_EXAMPLES = {"nq-amber-falcon-river-7291"}
# broker / prop-firm account ids: capital letters glued to a long number. A firm prefix (MFFU's MFFUEV..., Apex, Lucid, Topstep,
# Tradeify, TPT, FundedNext, Bulenox, ...) with 6+ digits, or any 4+ letters with 8+ digits. scrub() keeps the last 4 digits.
ACCT_ID_RX = re.compile(r"\b([A-Z]{2,16}-?)(\d{6,14})\b")
FIRMS = ("MFFU", "MYFF", "APEX", "PAAPEX", "LUCID", "LFT", "TOPSTEP", "TSX", "TRADEIFY", "TDY", "TPT", "FNXT", "FUNDEDNEXT", "BLN", "BULENOX",
         "EFF", "ELITE", "TICKTICK", "LEELOO", "TAKEPROFIT", "DTA", "FTMO", "TDV", "TRADOVATE", "RITHMIC", "NINJA", "NT8", "SIMACC")
USER_PATH_RX = re.compile(r"\b([A-Za-z]:(?:\\\\|\\|/)(?:[Uu]sers|Documents and Settings)(?:\\\\|\\|/))([^\\/\r\n\t\"'<>|:*?%$]{1,64}?)(?=\\|/)|"
                          r"(?<![\w.])(/Users/|/home/)([A-Za-z0-9._-]{1,64})(?=/)")
GENERIC_USERS = {"<you>", "you", "your", "yourname", "your_name", "your name", "user", "username", "<user>", "<username>", "name", "<name>",
                 "me", "public", "default", "default user", "all users", "runner", "runneradmin", "ubuntu", "root", "user1", "admin", "owner",
                 "example", "x", "...", "\u2026", "%username%", "$env:username", "${user}", "$user", "<me>", "pc", "bot", "trader", "dev",
                 "node", "app", "claude", "<your name>", "<windows user>", "<you>\\", "you\\"}
TAILNET_RX = re.compile(r"\b([a-z0-9-]{1,63})\.([a-z0-9-]{3,40})\.ts\.net\b")
SAFE_TAILNETS = {"tailnet", "your-tailnet", "example", "tailxxxx", "tail1234", "tailnet-name", "yourtailnet", "my-tailnet"}
TAILSCALE_IP_RX = re.compile(r"(?<![\d.])100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}(?![\d.])")
SAFE_TAILSCALE_IPS = {"100.100.100.100"}                         # Tailscale's own MagicDNS resolver address, not a device
SAFE_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", "example", "test", "localhost", "invalid", "email.com", "domain.com",
                      "yourdomain.com", "company.com", "users.noreply.github.com")
SAFE_PHONE_EXCHANGES = {"555"}                                   # 555-01xx: the fiction numbers
# the owner's age / birthday ("a Stingray before I turn 19 (Feb 22, 2027)" = a date of birth): never public
AGE_RX = re.compile(r"(?i)\b(?:before|by the time|until|when|after) I (?:turn|am|'m) \d{1,2}\b|\bI(?:'ll| will)? turn \d{1,2}\b|"
                    r"\bmy (?:date of )?birth(?:day|date)? is\b|\bdate of birth\b|\bborn (?:on|in) (?:\d|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)")
MASK = "\u2026"


def luhn(digits: str) -> bool:
    d = [int(c) for c in digits if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    s = 0
    for i, n in enumerate(reversed(d)):
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        s += n
    return s % 10 == 0


def acct_kind(letters: str, digits: str) -> str | None:
    """'broker account' | 'account id' | None for one ACCT_ID_RX match"""
    w = letters.rstrip("-")
    if w.startswith(FIRMS):
        return "broker account"
    if len(w) >= 4 and len(digits) >= 8:
        return "account id"
    return None


def masked(v) -> str:
    """what a report may print: the first 2 characters, the last 2 and the length"""
    s = str(v)
    if len(s) <= 4:
        return "*" * len(s)
    return s[:2] + "*" * min(12, len(s) - 4) + s[-2:] + f" ({len(s)} chars)"


class Finding(dict):
    """{"kind", "file", "where" (char offset), "value" (masked), "why"}"""

    def __str__(self):
        return f"{self['kind']:>17}  {self['file']}  @{self['where']}  {self['value']}  {self.get('why', '')}".rstrip()


def _add(out, kind, rel, pos, value, why=""):
    v = f"<{len(str(value))} chars>" if kind == "canary" else masked(value)      # a canary (the owner's name / email ...): not one letter
    out.append(Finding(kind=kind, file=rel, where=pos, value=v, why=why))


def _user_ok(user: str) -> bool:
    u = user.strip().lower()
    return u in GENERIC_USERS or u.startswith(("<", "%", "$", "{", "[")) or not u


def scan_text(text: str, rel: str, canaries=(), binary: bool = False) -> list:
    """Every finding in one file's text. canaries: [(label, value)] that must never appear (case-insensitive)."""
    out: list = []
    low = text.lower()
    for label, val in canaries:
        v = str(val or "").strip().lower()
        if len(v) < 4:
            continue
        i = low.find(v)
        if i >= 0:
            _add(out, "canary", rel, i, val, label)
        elif " " in v:                                     # a full name written with a dot / underscore / dash for the space
            first = v.split()[0]
            if first in low:
                m = re.search(r"[\s._-]+".join(re.escape(p) for p in v.split()), text, re.I)
                if m:
                    _add(out, "canary", rel, m.start(), m.group(0), label + " (other spelling)")
    for name, lit, rx in TOKEN_RX:
        if lit in text:
            for m in rx.finditer(text):
                _add(out, "token", rel, m.start(), m.group(0), name)
    if any(w in low for w in KEY_WORDS):
        for m in KEY_ASSIGN_RX.finditer(text):
            _add(out, "token", rel, m.start(), m.group(1), "a key / password assignment")
    if "@" in text:
        for m in EMAIL_RX.finditer(text):
            if m.start() and (text[m.start() - 1].isalnum() or text[m.start() - 1] in "._%+-"):
                continue
            dom = m.group(2).lower()
            if dom.endswith(SAFE_EMAIL_DOMAINS) or re.search(r"\.(png|jpe?g|webp|svg|gif|js|mjs|css|json|woff2?)$", dom) or re.match(r"^\d+x$", dom.split(".")[0]):
                continue
            _add(out, "email", rel, m.start(), m.group(0))
    if "nq-" in text:
        for m in NTFY_TOPIC_RX.finditer(text):
            if m.group(0) not in NTFY_EXAMPLES:
                _add(out, "ntfy topic", rel, m.start(), m.group(0), "the private alert topic shape")
    if binary:                                          # images, fonts, audio: the identity and secret checks above only
        return out
    for m in CARD_RX.finditer(text):
        digits = re.sub(r"\D", "", m.group(1))
        if luhn(digits) and len(set(digits)) > 1:
            _add(out, "card number", rel, m.start(), digits, "passes Luhn")
    for m in LONGNUM_RX.finditer(text):
        before = low[max(0, m.start() - 40):m.start()]
        w = ACCT_WORD_RX.search(before)
        if w and len(set(m.group(0))) > 2:
            _add(out, "account number", rel, m.start(), m.group(0), w.group(1))
    for m in PHONE_RX.finditer(text):
        if m.group(3) not in SAFE_PHONE_EXCHANGES:
            _add(out, "phone", rel, m.start(), m.group(0))
    for m in STREET_RX.finditer(text):
        _add(out, "street address", rel, m.start(), m.group(0))
    if " turn " in low or "birth" in low or "born " in low or " am " in low or "'m " in low:
        for m in AGE_RX.finditer(text):
            _add(out, "age / birthday", rel, m.start(), m.group(0), "with a date it is a date of birth")
    if ZIP_HINT_RX.search(text):
        for m in STATE_ZIP_RX.finditer(text):
            _add(out, "state + ZIP", rel, m.start(), m.group(0))
    for m in ACCT_ID_RX.finditer(text):
        k = acct_kind(m.group(1), m.group(2))
        if k:
            _add(out, k, rel, m.start(), m.group(0))
    if "sers" in text or "/home/" in text or "Documents and Settings" in text:
        for m in USER_PATH_RX.finditer(text):
            if not _user_ok(m.group(2) or m.group(4) or ""):
                _add(out, "user folder", rel, m.start(), m.group(0), "a personal folder name")
    if ".ts.net" in text:
        for m in TAILNET_RX.finditer(text):
            if m.group(2).lower() not in SAFE_TAILNETS and not m.group(2).startswith(("your", "<")):
                _add(out, "tailnet name", rel, m.start(), m.group(0))
    if "100." in text:
        for m in TAILSCALE_IP_RX.finditer(text):
            if m.group(0) not in SAFE_TAILSCALE_IPS:
                _add(out, "tailscale IP", rel, m.start(), m.group(0))
    return out


def _private_json(doc) -> str | None:
    if isinstance(doc, dict):
        k = str(doc.get("kind") or "")
        if k in PRIVATE_KINDS:
            return f"kind {k}"
        if doc.get("private") is True:
            return "marked private"
        bad = sorted(x for x in doc if str(x).lower() in SECRET_KEYS and doc.get(x))
        if bad:
            return "holds " + ", ".join(bad)
    return None


def private_file(rel: str, raw: bytes | None = None) -> str | None:
    """why this site file must not be public (its name, or its JSON content), else None"""
    name = os.path.basename(rel).lower()
    if name in PRIVATE_NAMES or name.endswith(PRIVATE_SUFFIXES) or name.startswith(".env") or \
            (name.endswith(DATA_EXT) and name.startswith(PRIVATE_PREFIXES)):
        return "a private file name"
    if raw is not None and name.endswith(".json") and len(raw) < 20_000_000 and any(h in raw for h in JSON_HINTS):
        try:
            return _private_json(json.loads(raw.decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            return None
    return None


JSON_HINTS = (b'"kind"', b'"private"') + tuple(b'"%s"' % k.encode() for k in sorted(SECRET_KEYS))


def _strings(raw: bytes, n: int = 8) -> str:
    return "\n".join(m.decode("ascii", "replace") for m in re.findall(rb"[\x20-\x7e]{%d,}" % n, raw))


def iter_files(site: str):
    for dp, dn, fn in os.walk(site):
        dn.sort()
        for n in sorted(fn):
            p = os.path.join(dp, n)
            yield p, os.path.relpath(p, site).replace(os.sep, "/")


def scan(site: str, canaries=(), allow=None) -> list:
    """Every finding in the built site. allow(finding) -> True drops a reviewed, harmless match (the test passes its short list)."""
    out: list = []
    for p, rel in iter_files(site):
        try:
            with open(p, "rb") as fh:
                raw = fh.read()
        except OSError:
            continue
        found = []
        why = private_file(rel, raw)
        if why:
            found.append(Finding(kind="private file", file=rel, where=0, value=os.path.basename(rel), why=why))
        if os.path.splitext(rel)[1].lower() in BINARY_EXT:
            found += scan_text(_strings(raw), rel, canaries, binary=True)
        else:
            found += scan_text(raw.decode("utf-8", "replace"), rel, canaries)
        out.extend(f for f in found if not (allow and allow(f)))
    return out


# ------------------------------------------------------------------------------------------------ canaries: what only this PC knows
BOT_IDENTITY = re.compile(r"(?i)(noreply|no-reply|anthropic\.com|github\.com|users\.noreply|actions@|bot@|\[bot\]|^claude$|^github$|"
                          r"^github actions$|^kalshi-to-jarvis$|liquidity-engine\.local)")


def _git(*args) -> str:
    try:
        r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except Exception:  # noqa: BLE001  (no git on the PC's zip copy: no git canaries)
        return ""


def _public_handles() -> set:
    """user names that are part of the site's own public addresses (<name>.github.io, github.com/<name>/): not canaries"""
    names = set()
    for p, _rel in iter_files(os.path.join(ROOT, "tools", "web_public")):
        if p.endswith((".js", ".html", ".json")) and os.path.getsize(p) < 3_000_000:
            try:
                s = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if "github" in s:
                names.update(x.lower() for x in re.findall(r"([A-Za-z0-9-]{3,39})\.github\.io", s))
                names.update(x.lower() for x in re.findall(r"github\.com/([A-Za-z0-9-]{3,39})/", s))
    return names


def _walk_strings(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from _walk_strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk_strings(v)
    elif isinstance(o, str):
        yield o


def state_canaries(state_path: str | None) -> list:
    """the broker account ids in a cloud / PC state.json or heartbeat file: their full form never goes public"""
    out, seen = [], set()
    try:
        with open(state_path, encoding="utf-8") as fh:
            st = json.load(fh)
    except Exception:  # noqa: BLE001
        return out
    for s in _walk_strings(st):
        for m in ACCT_ID_RX.finditer(s):
            if acct_kind(m.group(1), m.group(2)) and m.group(0) not in seen:
                seen.add(m.group(0))
                out.append(("a broker account of the state", m.group(0)))
    return out


def canaries(state_path: str | None = None, env=None, git: bool = True) -> list:
    """[(label, value)]: the owner's git names + emails (not the bots', not the site's public GitHub user name), the state's and this
    PC's heartbeat broker account ids, the private ntfy alert topic. Never printed. (This PC's user name is caught in its only public
    form, a folder C:\\Users\\<name>\\, by the folder detector: a bare first name would match the Greek names of the Cities.)"""
    env = os.environ if env is None else env
    out = []
    if git:
        handles = _public_handles()
        for line in sorted(set(_git("log", "--format=%an%x1f%ae%x1f%cn%x1f%ce").splitlines())):
            for i, v in enumerate(line.split("\x1f")):
                v = v.strip()
                if not v or BOT_IDENTITY.search(v):
                    continue
                if i % 2:
                    out.append(("a git author email", v))
                elif " " in v or (v.lower() not in handles and len(v) >= 5):
                    out.append(("a git author name", v))
    home = env.get("OLYMPUS_HOME") or os.path.join(env.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")
    try:
        with open(os.path.join(home, "ntfy.json"), encoding="utf-8") as fh:
            t = str((json.load(fh) or {}).get("topic") or "").strip()
        if len(t) >= 8:
            out.append(("the private ntfy alert topic", t))
    except Exception:  # noqa: BLE001
        pass
    for rel in ("logs/heartbeat_last.json", "logs/pc_hb/heartbeat.json"):
        out.extend(state_canaries(os.path.join(ROOT, *rel.split("/"))))
    if state_path:
        out.extend(state_canaries(state_path))
    uniq, seen = [], set()
    for label, v in out:
        if v.lower() not in seen:
            seen.add(v.lower())
            uniq.append((label, v))
    return uniq


# ------------------------------------------------------------------------------------------------ scrub (the build's last step)
def mask_account(s: str) -> str:
    """'MFFUEVBLDR123456789' -> 'MFFUEVBLDR…6789': the firm part and the last 4 digits, the way a bank shows a card"""
    return ACCT_ID_RX.sub(lambda m: (m.group(1) + MASK + m.group(2)[-4:]) if acct_kind(m.group(1), m.group(2)) else m.group(0), s)


def mask_paths(s: str) -> str:
    def rep(m):
        if m.group(1):
            return m.group(0) if _user_ok(m.group(2)) else m.group(1) + "<you>"
        return m.group(0) if _user_ok(m.group(4)) else m.group(3) + "<you>"
    return USER_PATH_RX.sub(rep, s)


def mask_emails(s: str) -> str:
    """'jane.doe@gmail.com' -> 'j***@gmail.com' (placeholder domains such as example.com stay)"""
    if "@" not in s:
        return s

    def rep(m):
        if m.start() and (s[m.start() - 1].isalnum() or s[m.start() - 1] in "._%+-"):
            return m.group(0)
        return m.group(0) if m.group(2).lower().endswith(SAFE_EMAIL_DOMAINS) else m.group(1)[0] + "***@" + m.group(2)
    return EMAIL_RX.sub(rep, s)


def mask_cards(s: str) -> str:
    """a card number (Luhn) in a text -> '…1111'"""
    def rep(m):
        digits = re.sub(r"\D", "", m.group(1))
        return (MASK + digits[-4:]) if luhn(digits) and len(set(digits)) > 1 else m.group(0)
    return CARD_RX.sub(rep, s)


def mask_age(s: str) -> str:
    """'2024 Stingray 3LT before I turn 19 (Feb 22, 2027)' -> '2024 Stingray 3LT (Feb 22, 2027)': the goal stays, the age goes"""
    return re.sub(r"\s*(?:" + AGE_RX.pattern[4:] + ")", "", s, flags=re.I) if AGE_RX.search(s) else s


def clean_string(s: str, extra=()) -> str:
    """the generic masks first (a broker id keeps its last 4 digits, an email its first letter, no age), then any other canary"""
    out = mask_age(mask_cards(mask_emails(mask_paths(mask_account(s)))))
    for v in extra:
        if v and len(v) >= 4 and v.lower() in out.lower():
            out = re.sub(re.escape(v), "<private>", out, flags=re.I)
    return out


def clean_obj(o, extra=()):
    """a JSON value with every string cleaned; a commit author ("who" next to a "sha") and secret-named keys dropped"""
    if isinstance(o, dict):
        d = {}
        for k, v in o.items():
            lk = str(k).lower()
            if lk in SECRET_KEYS and v:
                continue
            if lk in ("who", "author", "author_email", "committer") and "sha" in o:
                continue
            if lk in ("email", "author_email", "login", "user_login") and isinstance(v, str) and "@" in v:
                continue
            d[k] = clean_obj(v, extra)
        return d
    if isinstance(o, list):
        return [clean_obj(v, extra) for v in o]
    if isinstance(o, str):
        return clean_string(o, extra)
    return o


WHO_RX = re.compile(r'"(?:who|author|author_email|committer|email|login|user_login)"\s*:')


def _hits(text: str) -> int:
    n = sum(1 for m in ACCT_ID_RX.finditer(text) if acct_kind(m.group(1), m.group(2)))
    if "sers" in text or "/home/" in text:
        n += sum(1 for m in USER_PATH_RX.finditer(text) if not _user_ok(m.group(2) or m.group(4) or ""))
    if "@" in text:
        n += sum(1 for m in EMAIL_RX.finditer(text) if not m.group(2).lower().endswith(SAFE_EMAIL_DOMAINS))
    n += sum(1 for m in CARD_RX.finditer(text) if luhn(re.sub(r"\D", "", m.group(1))))
    n += len(AGE_RX.findall(text))
    return n + len(WHO_RX.findall(text))


LICENSE_RX = re.compile(r"(?i)(^|/)(OFL|LICEN[CS]E|NOTICE|COPYING|AUTHORS)[^/]*$")


STATUS_DROP = ("host", "hostname", "user", "login", "email", "account_name", "broker", "broker_account", "broker_line", "lit_account")


def public_status(obj, extra=()):
    """the dict tools/pc_report.py posts to the PUBLIC ntfy status topic: no PC name, no login, no broker account id, no folder"""
    def drop(o):
        if isinstance(o, dict):
            return {k: drop(v) for k, v in o.items() if str(k).lower() not in STATUS_DROP}
        if isinstance(o, list):
            return [drop(v) for v in o]
        return o
    return clean_obj(drop(obj), extra)


def scrub(site: str, extra=(), log=None, only=None) -> dict:
    """Mask / drop the private bits in a built site, in place. extra: more values to replace (canaries()); only: these site paths
    instead of every file. Never raises. -> {"files": rewritten, "removed": [...], "masked": n, "errors": [...]}"""
    rep = {"files": 0, "removed": [], "masked": 0, "errors": []}
    vals = tuple(v for _label, v in extra) if extra and isinstance(next(iter(extra)), (tuple, list)) else tuple(extra or ())
    vals = tuple(v for v in vals if v and len(str(v)) >= 4)
    files = list(iter_files(site)) if only is None else [(os.path.join(site, *r.split("/")), r) for r in only
                                                          if os.path.isfile(os.path.join(site, *r.split("/")))]
    for p, rel in files:
        try:
            with open(p, "rb") as fh:
                raw = fh.read()
            why = private_file(rel, raw)
            if why:
                os.remove(p)
                rep["removed"].append(f"{rel} ({why})")
                continue
            ext = os.path.splitext(rel)[1].lower()
            if ext not in TEXT_SCRUB_EXT or LICENSE_RX.search(rel):
                continue
            text = raw.decode("utf-8")
            low = text.lower()
            n = _hits(text) + sum(low.count(str(v).lower()) for v in vals)
            if not n:
                continue
            if ext == ".json":
                try:
                    doc = json.loads(text)
                except ValueError:
                    continue
                new_doc = clean_obj(doc, vals)
                if new_doc == doc:
                    continue
                pretty = "\n" in text.strip()
                new = json.dumps(new_doc, ensure_ascii=False, indent=1 if pretty else None, separators=None if pretty else (",", ":"))
            else:
                new = clean_string(text, vals)
                if new == text:
                    continue
            tmp = p + ".scrub.tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(new)
            os.replace(tmp, p)
            rep["files"] += 1
            rep["masked"] += n
            rep.setdefault("changed", []).append(rel)
        except Exception as e:  # noqa: BLE001  (a file it cannot read stays as it is: the test's scan still sees it)
            rep["errors"].append(f"{rel}: {e.__class__.__name__}")
    if log:
        log(f"  privacy: {rep['files']} files masked ({rep['masked']} values" + (": " + ", ".join(rep.get("changed", [])[:6]) if rep["files"] else "")
            + (" ..." if rep["files"] > 6 else "") + f"), {len(rep['removed'])} private files removed" + (": " + ", ".join(rep["removed"][:4]) if rep["removed"] else "")
            + (f", {len(rep['errors'])} unreadable" if rep["errors"] else ""))
    return rep


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="What may never be in the public site: scan or scrub a built site folder.")
    ap.add_argument("--scan", metavar="SITE")
    ap.add_argument("--scrub", metavar="SITE")
    ap.add_argument("--state", help="a state.json whose broker account ids are canaries too")
    a = ap.parse_args(argv)
    can = canaries(a.state) if (a.scan or a.scrub) else []
    if a.scrub:
        scrub(a.scrub, can, log=print)
    if a.scan:
        found = scan(a.scan, can)
        for f in found[:400]:
            print(f)
        print(f"{len(found)} findings in {a.scan}")
        return 1 if found else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
