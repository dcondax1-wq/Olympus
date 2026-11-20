"""PERSONALISED POSTCARDS for the Website Factory (day-a11y 2026-11-20): "<Business>, your new website is already built - scan to see it".

Why mail: the map leads have no email and most have no phone; cold AI calls need signed consent in Maryland. A postcard is legal to send
to a business, and its QR code opens the business's own concept site, where "Have our assistant call me" is the only way the AI caller
ever rings them.

  python tools/postcards.py samples [--out DIR]   3 sample cards (front + back PNG, and one PDF of all six sides): no key, nothing sent
  python tools/postcards.py setup                 POSTCARD_SETUP.bat: the provider's API key (typed hidden) -> %USERPROFILE%\\.olympus\\
                                                  postcards.json, the return address (a P.O. box: OWNER STEP), then the phrase gate:
                                                  SEND POSTCARDS = live; anything else = TEST mode (the provider's test key: nothing printed,
                                                  nothing mailed, nothing charged)
  python tools/postcards.py run                   one batch (weekdays, after 10:00 ET, once a day): up to 20 cards a day, 100 a week
  python tools/postcards.py stop | status         off / the counts (never the key)
Provider: Lob (https://docs.lob.com, 4x6 First-Class $0.909 a card on the free Developer plan, 11/2026; test keys are free).
Never again: the list the email autopilot keeps (agency_never.json + its opt-outs) is the same list here. Every card carries the sender,
the return address and a way to say "no more mail". The art is a clean agency brand (not the OLYMPUS look). Stdlib + Pillow + segno
(QR, free, made on this PC); POSTCARD_SETUP.bat installs both. Tests: tests/test_postcards.py (a fake provider, never the network).
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import getpass
import io
import json
import os
import re
import sys
import time
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
PHRASE = "SEND POSTCARDS"
CAP_DAY, CAP_WEEK = 20, 100
DPI = 300
W, H = int(6.25 * DPI), int(4.25 * DPI)              # 4x6 with the 1/8" bleed on every side (Lob's 4x6 template)
ADDR_ZONE = (W - int(3.55 * DPI), H - int(2.65 * DPI), W, H)   # the back's ink-free address + postage block (Lob 4x6: 3.2835" x 2.375", bottom right) + margin, kept blank
LOB_URL = "https://api.lob.com/v1/postcards"
SITE_BASE = "https://dcondax1-wq.github.io/jarvis"
BRAND = {"ink": (17, 24, 39), "muted": (75, 85, 99), "accent": (37, 99, 235), "paper": (255, 255, 255), "soft": (239, 246, 255)}   # a clean agency look


def home() -> str:
    return os.environ.get("OLYMPUS_HOME") or os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


def rj(p, default=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def wj(p, data, private=False):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    os.replace(p + ".tmp", p)
    if private:
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass


# ------------------------------------------------------------------------------------------------ config + the shared never-again list
def norm_cfg(raw) -> dict:
    c = dict(raw) if isinstance(raw, dict) else {}
    c["mode"] = c.get("mode") if c.get("mode") in ("off", "test", "live") else "off"
    c["provider"] = "lob"
    c["cap_day"] = max(1, min(CAP_DAY, int(c.get("cap_day") or CAP_DAY)))
    c["cap_week"] = max(1, min(CAP_WEEK, int(c.get("cap_week") or CAP_WEEK)))
    c.setdefault("site_base", SITE_BASE)
    return c


def cfg_problems(c: dict) -> list:
    p = []
    key = str(c.get("api_key") or "")
    if not key:
        p.append("the provider's API key")
    elif c.get("mode") == "live" and not key.startswith("live_"):
        p.append("a LIVE key (live_...) for live mode")
    elif c.get("mode") == "test" and not key.startswith("test_"):
        p.append("a TEST key (test_...) for test mode")
    r = c.get("return") or {}
    if not all(r.get(k) for k in ("line1", "city", "state", "zip")):
        p.append("the return address (a P.O. box is fine: OWNER STEP)")
    for k, label in (("from_name", "your name"), ("business_name", "your business name"), ("reply_email", "the email for 'no more mail'")):
        if not c.get(k):
            p.append(label)
    return p


def never_list() -> dict:
    """the ONE never-again list: agency_never.json (lead ids + emails, written by both senders) + the email autopilot's opt-outs"""
    n = rj(os.path.join(home(), "agency_never.json"), {}) or {}
    ids, emails = set(n.get("lead_ids") or []), set(n.get("emails") or [])
    st = rj(os.path.join(home(), "agency_mail_state.json"), {}) or {}
    emails |= set(st.get("suppress") or [])
    ids |= {lid for lid, c in (st.get("replied") or {}).items() if c in ("optout", "bounce")}
    return {"lead_ids": ids, "emails": emails}


def add_never(lead_id: str = "", email: str = "") -> None:
    p = os.path.join(home(), "agency_never.json")
    n = rj(p, {}) or {}
    ids, ems = set(n.get("lead_ids") or []), set(n.get("emails") or [])
    if lead_id:
        ids.add(lead_id)
    if email:
        ems.add(email.strip().lower())
    wj(p, {"v": 1, "lead_ids": sorted(ids), "emails": sorted(ems)})


# ------------------------------------------------------------------------------------------------ who can get a card
def mail_address(L: dict):
    """(address dict, '') when the lead has a full street address, else (None, why). Takes structured fields first (the leads team's
    reverse geocoding: addr = {line1, city, state, zip}), else cleans the map's one-line address."""
    a = L.get("addr") if isinstance(L.get("addr"), dict) else {}
    line1 = str(a.get("line1") or "").strip()
    city = str(a.get("city") or L.get("city") or L.get("town") or "").strip()
    state = str(a.get("state") or L.get("state") or "").strip()
    zp = str(a.get("zip") or L.get("zip") or L.get("postcode") or "").strip()
    if not line1:
        raw = str(L.get("address") or "").strip()
        if city and raw.lower().endswith(", " + city.lower()):
            raw = raw[: -len(city) - 2]
        m = re.match(r"^(\d+\w?),\s*((?:suite|unit|ste|apt)\s+\S+)\s+(.+)$", raw, re.I)
        line1 = f"{m.group(1)} {m.group(3)} {m.group(2).title()}" if m else raw.replace(", ", " ", 1) if re.match(r"^\d+\w?,", raw) else raw
    if not re.match(r"^\d+\w?\s+\S+", line1):
        return None, "no street address on the map yet"
    if not city or not re.fullmatch(r"[A-Z]{2}", state):
        return None, "no city / state"
    out = {"name": str(L.get("name") or "")[:40], "address_line1": line1[:64], "address_city": city[:200], "address_state": state, "address_country": "US"}
    if re.fullmatch(r"\d{5}(-\d{4})?", zp):
        out["address_zip"] = zp
    return out, ""


def demo_url(L: dict, sites: dict, base: str) -> tuple:
    own = (sites or {}).get(L.get("id")) or L.get("demo_url")
    b = str(base or SITE_BASE).rstrip("/")
    if isinstance(own, str) and re.match(r"^(https://|sites/|/|\.\./)", own):
        return (own if own.startswith("https://") else b + "/agency/" + re.sub(r"^(\.\./)+|^/?agency/", "", own.lstrip("/"))), True
    d = {"food": "restaurant", "auto": "detailer", "trades": "roofer", "home": "roofer", "realestate": "estate", "outdoor": "shed"}.get(L.get("niche") or "", "")
    return b + "/agency/demos/" + (d + "/" if d else ""), False


def pick(leads: list, sent: dict, never: dict, sites: dict, n: int, require_own_site: bool = True) -> tuple:
    """(cards to send [(lead, address, url)], skipped {reason: count}); hot leads first, never twice, never a 'no'"""
    out, skip = [], {}
    heat = {"hot": 0, "warm": 1, "cold": 2}
    for L in sorted([x for x in leads if isinstance(x, dict) and x.get("id")], key=lambda x: (heat.get(x.get("heat"), 3), -(float(x.get("score") or 0)), str(x.get("name")))):
        why = ""
        if L["id"] in sent:
            why = "already sent"
        elif L["id"] in never["lead_ids"] or (str(L.get("email") or "").lower() in never["emails"]):
            why = "said no (never again)"
        url, own = demo_url(L, sites, "")
        addr = None
        if not why and require_own_site and not own:
            why = "their own concept site is not built yet"
        if not why:
            addr, why = mail_address(L)
        if why:
            skip[why] = skip.get(why, 0) + 1
            continue
        if len(out) < n:
            out.append((L, addr))
    return out, skip


# ------------------------------------------------------------------------------------------------ the art (Pillow + segno)
FONTS = {"bold": ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf"],
         "reg": ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf"],
         "serif": ["DejaVuSerif-Bold.ttf", "georgiab.ttf", "Georgia Bold.ttf", "LiberationSerif-Bold.ttf"]}
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/liberation", "C:\\Windows\\Fonts", "/Library/Fonts", "/System/Library/Fonts/Supplemental"]


def font(kind: str, px: int):
    from PIL import ImageFont
    for n in FONTS[kind]:
        for d in FONT_DIRS:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, px)
    return ImageFont.load_default(size=px) if hasattr(ImageFont, "load_default") else ImageFont.load_default()


def wrap(draw, text: str, f, width: int) -> list:
    out, line, words = [], "", []
    for w in str(text).split():                         # a word wider than the column (a long link) is cut into pieces
        while draw.textlength(w, font=f) > width and len(w) > 4:
            k = len(w)
            while k > 4 and draw.textlength(w[:k], font=f) > width:
                k -= 1
            words.append(w[:k])
            w = w[k:]
        words.append(w)
    for w in words:
        t = (line + " " + w).strip()
        if draw.textlength(t, font=f) <= width or not line:
            line = t
        else:
            out.append(line)
            line = w
    if line:
        out.append(line)
    return out


def qr_image(url: str, px: int):
    import segno
    from PIL import Image
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=10, border=2, dark="#111827", light="#ffffff")
    buf.seek(0)
    return Image.open(buf).convert("RGB").resize((px, px), Image.NEAREST)


def render(L: dict, cfg: dict, url: str):
    """(front, back) PIL images, 1875 x 1275 (4x6 + bleed at 300 dpi)"""
    from PIL import Image, ImageDraw
    B = BRAND
    biz = str(L.get("name") or "Your business")
    # FRONT: the headline + the QR
    fr = Image.new("RGB", (W, H), B["paper"])
    d = ImageDraw.Draw(fr)
    d.rectangle([0, 0, W, int(0.42 * DPI)], fill=B["accent"])
    d.text((int(0.45 * DPI), int(0.13 * DPI)), str(cfg.get("business_name") or "[Business name]").upper(), font=font("bold", 44), fill=(255, 255, 255))
    q = int(2.2 * DPI)
    qx, qy = W - q - int(0.45 * DPI), int(0.85 * DPI)
    left, top = int(0.45 * DPI), int(0.75 * DPI)
    colw = qx - 30 - left - int(0.2 * DPI)
    size = 120
    f = font("serif", size)
    lines = wrap(d, f"{biz}, your new website is already built.", f, colw)
    while len(lines) > 4 and size > 70:
        size -= 8
        f = font("serif", size)
        lines = wrap(d, f"{biz}, your new website is already built.", f, colw)
    y = top
    for ln in lines:
        d.text((left, y), ln, font=f, fill=B["ink"])
        y += int(size * 1.15)
    y += 30
    for ln in wrap(d, "Scan the code to see it. It's free to look.", font("reg", 50), colw):
        d.text((left, y), ln, font=font("reg", 50), fill=B["muted"])
        y += 62
    d.rounded_rectangle([qx - 30, qy - 30, qx + q + 30, qy + q + 30], radius=40, fill=B["soft"])
    fr.paste(qr_image(url, q), (qx, qy))
    d.text((qx + q // 2, qy + q + 70), "Scan me", font=font("bold", 54), fill=B["accent"], anchor="mm")
    # BACK: the honest message across the top, the sender / return address / "no more mail" bottom left, the address block bottom right blank
    bk = Image.new("RGB", (W, H), B["paper"])
    d = ImageDraw.Draw(bk)
    x0, full = int(0.4 * DPI), W - int(0.8 * DPI)
    short = re.sub(r"^https?://", "", url).rstrip("/")
    y = int(0.38 * DPI)
    d.text((x0, y), f"Hi {biz},", font=font("bold", 48), fill=B["ink"])
    y += 72
    msg = (f"When people search for you online, there's no website to find. So we built you a draft, free to look at: scan the code on the "
           f"front or visit {short}. If you like it, it can be yours this week, with your photos and your own domain. Prefer a call? On the site, "
           f"tap \"Have our assistant call me\".")
    fm, lh = font("reg", 36), 46
    for ln in wrap(d, msg, fm, full):
        if y + lh > ADDR_ZONE[1] - 10:
            break
        d.text((x0, y), ln, font=fm, fill=B["ink"])
        y += lh
    col = ADDR_ZONE[0] - x0 - int(0.25 * DPI)
    y = ADDR_ZONE[1] + int(0.15 * DPI)
    for ln in wrap(d, f"{cfg.get('from_name') or '[Your name]'}, {cfg.get('business_name') or '[Business name]'}", font("bold", 34), col):
        d.text((x0, y), ln, font=font("bold", 34), fill=B["ink"])
        y += 44
    r = cfg.get("return") or {}
    ret = ", ".join(x for x in (r.get("line1"), r.get("city"), (r.get("state", "") + " " + r.get("zip", "")).strip()) if x) or "[P.O. box: owner step]"
    for ln in wrap(d, ret, font("reg", 30), col):
        d.text((x0, y), ln, font=font("reg", 30), fill=B["muted"])
        y += 40
    stop = f"Don't want mail from us? Email {cfg.get('reply_email') or '[your email]'} with \"STOP\" and your business name, and we'll never send another."
    lines = wrap(d, stop, font("reg", 28), col)
    y = max(y + 16, H - int(0.35 * DPI) - len(lines) * 36)
    for ln in lines:
        d.text((x0, y), ln, font=font("reg", 28), fill=B["muted"])
        y += 36
    d.line([x0, ADDR_ZONE[1] - 2, W - int(0.4 * DPI), ADDR_ZONE[1] - 2], fill=(229, 231, 235), width=3)
    return fr, bk


def png(img) -> bytes:
    b = io.BytesIO()
    img.save(b, format="PNG", dpi=(DPI, DPI))
    return b.getvalue()


# ------------------------------------------------------------------------------------------------ the provider (Lob)
def multipart(fields: dict, files: dict) -> tuple:
    bnd = "----olympus" + uuid.uuid4().hex
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f"--{bnd}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for k, (name, data, ctype) in files.items():
        out.write(f"--{bnd}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{name}\"\r\nContent-Type: {ctype}\r\n\r\n".encode())
        out.write(data)
        out.write(b"\r\n")
    out.write(f"--{bnd}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={bnd}"


def lob_send(cfg: dict, to: dict, front: bytes, back: bytes, lead_id: str, opener=None) -> dict:
    """one postcard; with a test_ key Lob prints and mails nothing and charges nothing. Returns {id, test} or raises"""
    r = cfg["return"]
    fields = {"description": f"website draft {lead_id}"[:255], "size": "4x6", "mail_type": "usps_first_class", "use_type": "marketing", "metadata[lead_id]": lead_id[:500]}
    for k, v in to.items():
        fields[f"to[{k}]"] = v
    for k, v in {"name": cfg["business_name"], "address_line1": r["line1"], "address_city": r["city"], "address_state": r["state"], "address_zip": r["zip"], "address_country": "US"}.items():
        fields[f"from[{k}]"] = v
    body, ctype = multipart(fields, {"front": ("front.png", front, "image/png"), "back": ("back.png", back, "image/png")})
    req = urllib.request.Request(LOB_URL, data=body, method="POST", headers={"Content-Type": ctype,
                                 "Authorization": "Basic " + base64.b64encode((cfg["api_key"] + ":").encode()).decode()})
    with (opener or urllib.request.urlopen)(req, timeout=60) as resp:
        j = json.loads(resp.read().decode("utf-8") or "{}")
    return {"id": j.get("id", ""), "test": str(cfg["api_key"]).startswith("test_")}


# ------------------------------------------------------------------------------------------------ one batch
def et_now(now=None):
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/New_York")
    except Exception:  # noqa: BLE001
        tz = dt.timezone(dt.timedelta(hours=-5))
    n = now or dt.datetime.now(dt.timezone.utc)
    return n.astimezone(tz)


def run_once(cfg: dict, state: dict, leads: list, sites: dict, now=None, send=None) -> dict:
    """weekdays from 10:00 ET, once a day: up to cap_day cards (cap_week a Mon-Sun week); state changed in place"""
    res = {"sent": [], "skipped": {}, "errors": [], "mode": cfg.get("mode")}
    if cfg.get("mode") not in ("test", "live"):
        return res
    probs = cfg_problems(cfg)
    if probs:
        res["errors"].append("setup incomplete: " + ", ".join(probs))
        return res
    if cfg["mode"] == "live" and state.get("phrase") != PHRASE:
        res["errors"].append("live needs the phrase SEND POSTCARDS (POSTCARD_SETUP.bat)")
        return res
    e = et_now(now)
    day, week = e.strftime("%Y-%m-%d"), e.strftime("%G-W%V")
    if e.weekday() >= 5 or e.hour < 10 or state.get("last_day") == day:
        return res
    sent_week = sum(1 for x in state.get("sent", {}).values() if x.get("week") == week and not x.get("test"))
    room = min(cfg["cap_day"], cfg["cap_week"] - sent_week) if cfg["mode"] == "live" else min(3, cfg["cap_day"])   # test mode: 3 a day
    todo, res["skipped"] = pick(leads, {k: v for k, v in state.get("sent", {}).items() if not v.get("test")}, never_list(), sites, max(0, room))
    for L, addr in todo:
        url, _ = demo_url(L, sites, cfg.get("site_base"))
        try:
            fr, bk = render(L, cfg, url)
            r = (send or lob_send)(cfg, addr, png(fr), png(bk), L["id"])
            state.setdefault("sent", {})[L["id"] + ("#test" + day if r.get("test") else "")] = {"d": day, "week": week, "id": r.get("id", ""), "test": bool(r.get("test"))}
            res["sent"].append({"lead": L.get("name"), "test": bool(r.get("test"))})
        except Exception as ex:  # noqa: BLE001
            msg = str(ex)[:160].replace(str(cfg.get("api_key") or "~"), "[secret]")
            res["errors"].append(f"{L.get('name')}: {msg}")
    state["last_day"] = day
    return res


# ------------------------------------------------------------------------------------------------ commands
def leads_and_sites() -> tuple:
    leads = (rj(os.path.join(WEB, "agency", "leads", "leads.json"), {}) or {}).get("leads") or []
    s = (rj(os.path.join(WEB, "agency", "sites", "index.json"), {}) or {}).get("sites")
    if isinstance(s, list):
        s = {x.get("id"): x.get("url") for x in s if isinstance(x, dict)}
    return leads, s if isinstance(s, dict) else {}


def samples(out_dir: str, cfg: dict | None = None) -> list:
    """3 sample cards from the real leads (or made-up ones): front + back PNG each and one 6-page PDF. No key, nothing sent"""
    from PIL import Image  # noqa: F401
    cfg = cfg or {"business_name": "[Business name]", "from_name": "[Your name]", "reply_email": "[your email]", "return": {}}
    leads, sites = leads_and_sites()
    pickd = [L for L in leads if L.get("name")][:3] or [{"id": f"x{i}", "name": n, "niche": "food"} for i, n in enumerate(("Joe's Diner", "Bright Smile Dental", "Peak Fitness"))]
    os.makedirs(out_dir, exist_ok=True)
    pages, files = [], []
    for i, L in enumerate(pickd, 1):
        url, _ = demo_url(L, sites, cfg.get("site_base") or SITE_BASE)
        fr, bk = render(L, cfg, url)
        for side, im in (("front", fr), ("back", bk)):
            p = os.path.join(out_dir, f"card{i}-{side}.png")
            im.reduce(2).save(p, format="PNG", optimize=True)   # half size for the repo (the real upload is the full 300 dpi)
            files.append(p)
            pages.append(im.reduce(2).convert("RGB"))
    pdf = os.path.join(out_dir, "sample-cards.pdf")
    pages[0].save(pdf, save_all=True, append_images=pages[1:], resolution=DPI // 2)   # a preview (6.25 x 4.25 in pages); the upload is full 300 dpi
    files.append(pdf)
    return files


def cmd_setup(ask=input, secret=getpass.getpass, out=print) -> int:
    p = os.path.join(home(), "postcards.json")
    old = norm_cfg(rj(p, {}))
    out("POSTCARDS setup. Everything stays on this PC (%USERPROFILE%\\.olympus\\postcards.json). Nothing is sent now.")
    out("Lob (lob.com, free Developer plan): Settings > API Keys. A TEST key (test_...) mails nothing; a LIVE key (live_...) mails for real.")

    def q(label, cur):
        v = ask(f"  {label}{' [' + cur + ']' if cur else ''}: ").strip()
        return v or cur
    c = dict(old)
    k = secret("  Lob API key (hidden as you type; Enter = keep the saved one): ").strip()
    c["api_key"] = k or old.get("api_key", "")
    c["from_name"] = q("Your name", old.get("from_name", ""))
    c["business_name"] = q("Your business name (on the card)", old.get("business_name", ""))
    c["reply_email"] = q("Email for 'no more mail' requests", old.get("reply_email", ""))
    r = dict(old.get("return") or {})
    out("  Return address (OWNER STEP: a P.O. box keeps your home address off the cards):")
    for key, label in (("line1", "Street or PO Box"), ("city", "City"), ("state", "State (2 letters)"), ("zip", "ZIP")):
        r[key] = q("    " + label, r.get(key, ""))
    c["return"] = r
    out("  Type SEND POSTCARDS to mail real cards (max 20 a day, 100 a week; needs a live_ key). Anything else = TEST mode (nothing mailed).")
    phrase = ask("  > ").strip()
    c["mode"] = "live" if phrase == PHRASE else "test"
    c = norm_cfg(c)
    probs = cfg_problems(c)
    if probs:
        c["mode"] = "off"
        out("  Saved, but OFF: missing " + ", ".join(probs) + ".")
    wj(p, c, private=True)
    st = rj(os.path.join(home(), "postcards_state.json"), {}) or {}
    st["phrase"] = PHRASE if c["mode"] == "live" else ""
    wj(os.path.join(home(), "postcards_state.json"), st)
    if not probs:
        out(f"  [OK] Saved. Mode: {c['mode'].upper()}{' (real cards, real postage)' if c['mode'] == 'live' else ' (test key: nothing printed or mailed)'}.")
    return 1 if probs else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Personalised postcards (OFF until POSTCARD_SETUP.bat; live only after SEND POSTCARDS)")
    ap.add_argument("cmd", choices=["samples", "setup", "run", "stop", "status"])
    ap.add_argument("--out", default=os.path.join(ROOT, "scratch", "postcards"))
    a = ap.parse_args(argv)
    p, sp = os.path.join(home(), "postcards.json"), os.path.join(home(), "postcards_state.json")
    if a.cmd == "samples":
        for f in samples(a.out, norm_cfg(rj(p, {})) if os.path.exists(p) else None):
            print(" ", f)
        return 0
    if a.cmd == "setup":
        return cmd_setup()
    cfg = norm_cfg(rj(p, {}))
    if a.cmd == "stop":
        cfg["mode"] = "off"
        wj(p, cfg, private=True)
        print("  [OK] Postcards OFF.")
        return 0
    st = rj(sp, {}) or {}
    leads, sites = leads_and_sites()
    if a.cmd == "status":
        _, skip = pick(leads, {k: v for k, v in st.get("sent", {}).items() if not v.get("test")}, never_list(), sites, 0)
        real = sum(1 for v in st.get("sent", {}).values() if not v.get("test"))
        print(f"  Mode {cfg['mode'].upper()} · {real} real cards sent · not mailable yet: " + ", ".join(f"{n} {w}" for w, n in skip.items()))
        return 0
    res = run_once(cfg, st, leads, sites)
    wj(sp, st)
    print(f"  mode {res['mode']}: sent {len(res['sent'])}" + (f", problems: {res['errors'][:2]}" if res["errors"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
