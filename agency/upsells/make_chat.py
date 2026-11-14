"""Front-desk chat: build one client's chat widget (one <script> tag on their site).

    python agency/upsells/make_chat.py data/agency/clients/joes-barbers.json             -> data/agency/upsells/joes-barbers/
    python agency/upsells/make_chat.py client.json --out <folder>                         another output folder
    python agency/upsells/make_chat.py client.json --site <site folder>                   also install it into a site folder (index.html)
    python agency/upsells/make_chat.py --new barber|plumber_hvac|restaurant <id> "Name"   a starter client file to fill in

Writes chat-<id>.js (the widget, < 25 KB), chat-<id>-form.html (the hidden Netlify form the site needs once),
chat-<id>-preview.html (every answer on one page, to check with the client) and chat-<id>-install.txt (the 2 lines to paste).
The widget answers from the facts in the client file only. Anything the file does not say is not claimed: a preset FAQ whose
fact is missing is left out and listed under "check with the client".
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from agency.upsells import common as K  # noqa: E402

PRESETS = os.path.join(HERE, "presets")
RUNTIME = os.path.join(HERE, "chat", "widget.min.js")
BUDGET = 25_000                                   # bytes, the whole built file (runtime + this client's data)
KINDS_NEED = {"area": "area", "pay": "payments", "services": "services"}
TOKEN = re.compile(r"\{([a-z_]+)\}")
DYNAMIC = {"status", "next_open", "today"}        # filled by the widget at the moment of the question


SYN = {"u": "you", "r": "are", "ur": "your", "wat": "what", "whats": "what is", "tmrw": "tomorrow", "tmr": "tomorrow", "tommorow": "tomorrow",
       "2day": "today", "tonite": "tonight", "hrs": "hours", "appt": "appointment", "pls": "please", "plz": "please", "thx": "thanks", "ty": "thanks"}


def norm(s: str) -> str:
    """the widget's norm() in Python (tests/test_agency_upsells.py checks both give the same words)"""
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or "").lower())
    s = re.sub(r"[̀-ͯ]", "", s)
    s = re.sub(r"['’`]", "", s).replace("&", " and ").replace("$", " dollar ")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def stem(w: str) -> str:
    """the widget's stem() in Python"""
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    o = w
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    if w != o and re.search(r"([b-df-hj-km-np-tv-z])\1$", w) and not re.search(r"(ll|ss|zz)$", w):
        w = w[:-1]
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]
    return w


def signature(key: str) -> tuple:
    """what the widget sees in a key: the stems of its words (two keys with one signature are the same key)"""
    out = []
    for w in norm(key).split(" "):
        if w:
            out.extend(stem(x) for x in SYN.get(w, w).split(" "))
    return tuple(out)


def lean_keys(keys: list) -> list:
    """drop keys the widget would read the same way (hours / hour, prices / price / pricing ...), keep the strongest weight"""
    best: dict = {}
    for k in keys:
        m = re.match(r"^(.*):([0-9.]+)$", k)
        text, wt = (m.group(1), float(m.group(2))) if m else (k, 1.0)
        sig = signature(text)
        if not sig:
            continue
        if sig not in best or wt > best[sig][1]:
            best[sig] = (text.strip(), wt)
    return [t if w == 1.0 else f"{t}:{w:g}" for t, w in best.values()]


def preset_names() -> list:
    return sorted(f[:-5] for f in os.listdir(PRESETS) if f.endswith(".json") and not f.startswith("_"))


def find_preset(chat: dict, trade: str) -> dict:
    name = (chat.get("preset") or "").strip().lower()
    if name:
        path = os.path.join(PRESETS, name + ".json")
        if not os.path.isfile(path):
            raise K.ClientError(f"chat.preset {name!r} does not exist (have: {', '.join(preset_names())})")
        return K.load_json(path)
    t = (trade or "").strip().lower()
    for p in preset_names():
        data = K.load_json(os.path.join(PRESETS, p + ".json"))
        if t and any(t == x or x in t for x in data.get("trades", [])):
            return data
    return {"preset": "", "label": "General", "intents": [], "facts": {}, "chips": None}


def join_list(items) -> str:
    items = [str(x).strip() for x in items or [] if str(x).strip()]
    if len(items) <= 2:
        return " and ".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def day_text(ranges) -> str:
    if not ranges:
        return "closed"
    if ranges == [[0, 1440]]:
        return "24 hours"
    return " and ".join(f"{K.fmt_time(a)}–{K.fmt_time(b)}" for a, b in ranges)


def build_config(client: dict) -> tuple:
    """-> (config dict for the widget, warnings, report rows for the preview)"""
    chat = dict(client.get("chat") or {})
    base = K.load_json(os.path.join(PRESETS, "_base.json"))
    pre = find_preset(chat, client.get("trade", ""))
    warnings: list = []
    pal = K.palette(chat.get("brand_color") or "#0f766e")
    week = K.parse_hours(chat.get("hours"))
    closed = {}
    for d, note in (chat.get("closed_dates") or {}).items():
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            raise K.ClientError(f"closed_dates: {d!r} must look like 2026-12-25")
        closed[d] = str(note or "")
    phone = K.tel(client["phone"])
    text_phone = chat.get("text_phone", client["phone"])
    emergency = chat.get("emergency_phone") or ""
    area = chat.get("area") or None
    if area and not (area.get("text") or "").strip():
        raise K.ClientError("chat.area needs a 'text', like \"Tampa, Brandon and Riverview\"")
    services = []
    for s in chat.get("services") or []:
        if not s.get("name") or not s.get("price"):
            raise K.ClientError(f"each service needs a name and a price ({s})")
        named = signature(s["name"])
        services.append([s["name"], s["price"], s.get("time", ""), "|".join(k for k in lean_keys(s.get("keys") or []) if signature(k) != named)])
    booking = (chat.get("booking_url") or "").strip()
    for label, url in (("booking_url", booking), ("maps_url", chat.get("maps_url") or ""), ("menu_url", chat.get("menu_url") or "")):
        if url and not re.match(r"^(https?://|/)", url):
            raise K.ClientError(f"chat.{label} must start with https:// (or / for a page on the same site)")
    facts = dict(pre.get("facts") or {})
    facts.update(chat.get("facts") or {})
    static = {
        "name": client["name"], "phone": client["phone"], "text_phone": text_phone or client["phone"], "email": client.get("email", ""),
        "city": client.get("city", ""), "address": chat.get("address", ""), "area": (area or {}).get("text", ""),
        "payments": join_list(chat.get("payments")), "booking_label": chat.get("booking_label") or pre.get("sample", {}).get("booking_label") or "Book online",
        "emergency_phone": emergency or client["phone"], "menu_url": chat.get("menu_url", ""), "site_url": client.get("site_url", ""),
    }

    def fill(text: str):
        """static tokens now (a fact may hold a token itself, like {phone}); the widget's own ({status}...) stay; None when a fact is missing"""
        out = str(text)
        for _ in range(4):
            missing: list = []

            def sub(m):
                k = m.group(1)
                if k in DYNAMIC:
                    return m.group(0)
                v = facts.get(k, static.get(k))
                if v is None or str(v).strip() == "":
                    missing.append(k)
                    return m.group(0)
                return str(v)
            new = TOKEN.sub(sub, out)
            if missing:
                return None, sorted(set(missing))
            if new == out:
                break
            out = new
        return out, []

    off = set(pre.get("off") or []) | set(chat.get("off") or [])
    order: list = []
    intents: dict = {}
    for it in pre.get("intents", []):
        intents[it["id"]] = dict(it, kind=it.get("kind", "faq"))
        order.append(it["id"])
    for it in chat.get("faqs") or []:                         # the client's own extra FAQs
        if not it.get("id") or not it.get("a") or not it.get("keys"):
            raise K.ClientError(f"each chat.faqs item needs id, a (the answer) and keys ({it})")
        intents[it["id"]] = dict(it, kind="faq")
        if it["id"] not in order:
            order.insert(0, it["id"])
    for it in base["intents"]:
        merged = dict(it)
        if it["id"] in pre and isinstance(pre[it["id"]], dict):  # a preset's change to a base intent (restaurant 'book')
            extra = pre[it["id"]]
            merged["keys"] = list(it["keys"]) + list(extra.get("keys", []))
            merged["chip"] = extra.get("chip", it.get("chip"))
        intents.setdefault(it["id"], merged)
        order.append(it["id"])
    report, out_int = [], []
    for iid in order:
        it = intents[iid]
        kind = it["kind"]
        if iid in off:
            continue
        need = KINDS_NEED.get(kind)
        if need and not chat.get(need):
            warnings.append(f"'{iid}' answers are off: the client file has no chat.{need}")
            continue
        answer = ""
        if kind == "faq":
            override = (chat.get("answers") or {}).get(iid)
            answer, missing = fill(override or it["a"])
            if answer is None:
                warnings.append(f"'{iid}' FAQ is off until the client file says it: chat.facts.{missing[0]}" + (f" (+{', '.join(missing[1:])})" if missing[1:] else ""))
                continue
        acts = []
        for a in it.get("act") or []:
            ok = {"book": bool(booking), "text": bool(text_phone), "map": bool(chat.get("maps_url")), "menu": bool(chat.get("menu_url")),
                  "emergency": True, "call": True, "lead": True}.get(a)
            if ok is None:
                raise K.ClientError(f"{iid}: unknown action {a!r}")
            if ok:
                acts.append(a)
            elif a == "book":
                acts.append("call")
        chip = (chat.get("chip_labels") or {}).get(iid, it.get("chip", ""))
        keys = lean_keys([k.strip() for k in it["keys"] if k.strip()])
        short_kind = "" if (kind == "faq" and answer) or (kind == iid and kind != "faq") else kind   # the widget fills it back in
        out_int.append([iid, short_kind, chip or "", "|".join(keys), answer, " ".join(dict.fromkeys(acts))])
        report.append({"id": iid, "kind": kind, "chip": chip, "answer": answer, "acts": acts, "keys": keys, "optional": bool(it.get("a")) and iid not in (chat.get("faqs_keep") or [])})
    present = {r[0] for r in out_int}
    chips = [c for c in (chat.get("chips") or pre.get("chips") or base["chips"]) if c in present and next(r for r in out_int if r[0] == c)[2]]
    dropped = [c for c in (chat.get("chips") or pre.get("chips") or base["chips"]) if c not in chips]
    if dropped:
        warnings.append(f"quick buttons left out (no answer for them yet): {', '.join(dropped)}")

    def text(key, default_src):
        out, missing = fill(chat.get(key) or default_src)
        if out is None:
            raise K.ClientError(f"chat.{key}: fill {', '.join(missing)}")
        return out

    cfg = {
        "id": client["id"], "n": client["name"], "city": client.get("city", ""),
        "col": {"f": pal["fill"], "i": pal["ink"], "a": pal["accent"], "s": pal["soft"]},
        "font": chat.get("font", ""), "tz": chat.get("timezone") or "America/New_York",
        "h": week, "dt": [day_text(d) for d in week], "wk": K.week_text(week), "x": closed,
        "ph": phone, "phl": client["phone"], "sm": K.tel(text_phone) if text_phone else "", "sml": text_phone or "",
        "em": K.tel(emergency) if emergency else "", "eml": emergency,
        "bk": booking, "bkl": static["booking_label"], "mp": chat.get("maps_url", ""), "ad": chat.get("address", ""), "dn": chat.get("directions", ""),
        "mu": chat.get("menu_url", ""), "ar": {"t": area["text"], "w": area.get("towns", []), "z": [str(z) for z in area.get("zips", [])]} if area else None,
        "pay": static["payments"], "sv": services, "pn": chat.get("prices_note", ""),
        "g": text("greeting", pre.get("greeting") or base["greeting"]), "ah": text("after_hours", pre.get("after_hours") or base["after_hours"]),
        "fb": text("fallback", base["fallback"]), "ch": chips, "it": out_int,
        "f": {"n": chat.get("form_name") or "frontdesk-chat", "a": chat.get("form_action") or "/"},
    }
    try:
        import zoneinfo
        zoneinfo.ZoneInfo(cfg["tz"])
    except Exception:
        raise K.ClientError(f"chat.timezone {cfg['tz']!r} is not a time zone name (like America/New_York)")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", cfg["f"]["n"]):
        raise K.ClientError("chat.form_name: letters, digits, - and _ only")
    return cfg, warnings, report


def build_js(cfg: dict) -> str:
    runtime = open(RUNTIME, encoding="utf-8").read()
    data = json.dumps(cfg, ensure_ascii=False, separators=(",", ":"))
    data = data.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    if runtime.count("__FDC_CONFIG__") != 1:
        raise RuntimeError("chat/widget.min.js has no single __FDC_CONFIG__ slot (rebuild it: see docs/AGENCY_UPSELLS.md)")
    return runtime.replace("__FDC_CONFIG__", data)


def form_snippet(cfg: dict) -> str:
    return (f'<!-- Front-desk chat: the lead form Netlify needs to see once (hidden; the chat sends to it). Paste anywhere inside <body>. -->\n'
            f'<form name="{cfg["f"]["n"]}" data-netlify="true" netlify-honeypot="bot-field" hidden>\n'
            f'  <input type="text" name="name"><input type="tel" name="phone"><textarea name="need"></textarea>\n'
            f'  <input type="text" name="page"><textarea name="chat"></textarea><input type="text" name="bot-field">\n'
            f'</form>')


def script_tag(cfg: dict, src: str = "") -> str:
    return f'<script src="{src or "/chat-" + cfg["id"] + ".js"}" defer></script>'


def preview_html(client: dict, cfg: dict, report: list, warnings: list, js_name: str) -> str:
    rows = []
    for r in report:
        ans = r["answer"] or {"hours": "Today's status + the week: " + "; ".join(cfg["wk"]), "prices": "The price list (or the price of the service asked about)",
                              "services": "The services list (or 'yes, we do that' for one of them)", "area": "Yes/no for a town or ZIP, else: " + ((cfg.get("ar") or {}).get("t") or ""),
                              "book": cfg["bkl"] + " button" if cfg["bk"] else "Call / text / leave your number", "dir": cfg["ad"] or "We come to you",
                              "pay": "We take " + cfg["pay"], "contact": "Call " + cfg["phl"], "lead": "The leave-your-number form",
                              "greet": "Hi! What can I help you with?", "thanks": "You're welcome!", "bye": "Thanks for stopping by."}.get(r["kind"], "")
        rows.append(f"<tr><td><b>{K.esc(r['chip'] or r['id'])}</b><br><small>{K.esc(', '.join(r['keys'][:6]))}{'…' if len(r['keys']) > 6 else ''}</small></td>"
                    f"<td>{K.esc(ans)}</td><td>{K.esc(' '.join(r['acts']))}</td></tr>")
    warn = "".join(f"<li>{K.esc(w)}</li>" for w in warnings) or "<li>Nothing missing.</li>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chat answers: {K.esc(client['name'])}</title>
<style>body{{font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;margin:0;padding:16px;background:#f6f7f9;color:#1f2430}}
main{{max-width:900px;margin:0 auto}}h1{{font-size:22px;margin:4px 0 6px}}p{{margin:6px 0}}table{{border-collapse:collapse;width:100%;background:#fff;border-radius:12px;overflow:hidden}}
td,th{{border-bottom:1px solid #e5e7eb;padding:10px;text-align:left;vertical-align:top}}th{{background:#eef1f4;font-size:13px}}small{{color:#5c6573}}
.box{{background:#fff;border-radius:12px;padding:12px 16px;margin:12px 0}}</style></head>
<body><main>
<h1>Front-desk chat: {K.esc(client['name'])}</h1>
<p>Check every answer with the client before the chat goes live. The chat bubble (bottom corner) is the real widget: try it.</p>
<div class="box"><b>Hours as the chat reads them</b> ({K.esc(cfg['tz'])}): {K.esc(' · '.join(cfg['wk']))}</div>
<div class="box"><b>Check with the client</b><ul>{warn}</ul></div>
<table><tr><th>Question (some of the words it reacts to)</th><th>Answer</th><th>Buttons</th></tr>{''.join(rows)}</table>
</main>
<script src="{K.esc(js_name)}" defer></script>
</body></html>
"""


def install_text(cfg: dict) -> str:
    return (f"Front-desk chat for {cfg['n']} ({cfg['id']})\n\n"
            f"1. Upload chat-{cfg['id']}.js to the site's main folder.\n"
            f"2. Paste these lines just before </body> on every page (or the site's shared footer):\n\n"
            f"{script_tag(cfg)}\n{form_snippet(cfg)}\n\n"
            f"3. Deploy, then send one test lead from the chat: it shows up in Netlify under Forms > {cfg['f']['n']}.\n"
            f"   (Netlify: Site configuration > Notifications > Form submission notifications, to get each lead by email.)\n")


def install_into_site(site: str, cfg: dict, js: str) -> str:
    idx = os.path.join(site, "index.html")
    if not os.path.isfile(idx):
        raise K.ClientError(f"no index.html in {site}")
    K.write(os.path.join(site, f"chat-{cfg['id']}.js"), js)
    skip = {"review", "kit", "print", "node_modules", ".git"}                # the review page and the owner's kit get no chat bubble
    pages = []
    for dp, dirs, fs in os.walk(site):
        dirs[:] = sorted(d for d in dirs if d not in skip and not d.startswith("."))
        pages += [os.path.join(dp, f) for f in sorted(fs) if f.endswith(".html") and not f.startswith("chat-")
                  and "</body>" in open(os.path.join(dp, f), encoding="utf-8").read().lower()]
    for page in pages:
        rel = os.path.relpath(os.path.join(site, f"chat-{cfg['id']}.js"), os.path.dirname(page)).replace(os.sep, "/")
        html = open(page, encoding="utf-8").read()
        block = script_tag(cfg, rel) + ("\n" + form_snippet(cfg) if page == idx else "")
        K.write(page, K.insert_block(html, "frontdesk-chat", block))
    return idx


def fit_budget(cfg: dict, warnings: list) -> str:
    """the built file must stay under BUDGET bytes: if a client's facts are long, the last optional FAQs (not a quick button) wait outside"""
    js, left_out = build_js(cfg), []
    while len(js.encode("utf-8")) > BUDGET:
        optional = [r for r in cfg["it"] if r[4] and r[0] not in cfg["ch"]]
        if not optional:
            raise K.ClientError(f"the widget would be {len(js.encode('utf-8')):,} bytes, over the {BUDGET:,} budget: shorten answers, services or keys")
        cfg["it"].remove(optional[-1])
        left_out.append(optional[-1][0])
        js = build_js(cfg)
    if left_out:
        warnings.append(f"left out to keep the widget under {BUDGET:,} bytes: {', '.join(left_out)} (shorten other answers or keys to bring them back)")
    return js


def build(client_path: str, out: str | None = None, site: str | None = None, quiet: bool = False) -> dict:
    client = K.load_client(client_path)
    cfg, warnings, report = build_config(client)
    js = fit_budget(cfg, warnings)
    kept = {r[0] for r in cfg["it"]}
    report = [r for r in report if r["id"] in kept]
    size = len(js.encode("utf-8"))
    out = out or K.default_out(client)
    name = f"chat-{cfg['id']}.js"
    K.write(os.path.join(out, name), js)
    K.write(os.path.join(out, f"chat-{cfg['id']}-form.html"), form_snippet(cfg) + "\n")
    K.write(os.path.join(out, f"chat-{cfg['id']}-preview.html"), preview_html(client, cfg, report, warnings, name))
    K.write(os.path.join(out, f"chat-{cfg['id']}-install.txt"), install_text(cfg))
    if site:
        install_into_site(site, cfg, js)
    res = {"out": out, "file": os.path.join(out, name), "bytes": size, "gzip": len(gzip.compress(js.encode("utf-8"), 9, mtime=0)),
           "intents": len(cfg["it"]), "chips": cfg["ch"], "warnings": warnings}
    if not quiet:
        print(f"chat-{cfg['id']}.js: {size:,} bytes ({res['gzip']:,} gzipped), {res['intents']} answers, buttons: {', '.join(cfg['ch'])}")
        for w in warnings:
            print("  check with the client:", w)
        print(f"  written to {out}" + (f"; installed into {site}" if site else ""))
    return res


def new_client(preset: str, cid: str, name: str, path: str | None = None) -> str:
    pre_path = os.path.join(PRESETS, preset + ".json")
    if not os.path.isfile(pre_path):
        raise K.ClientError(f"no preset {preset!r} (have: {', '.join(preset_names())})")
    pre = K.load_json(pre_path)
    sample = json.loads(json.dumps(pre.get("sample", {})))
    client = {"id": cid, "name": name, "trade": preset.split("_")[0], "city": "FILL: City, ST", "phone": "FILL: (555) 555-0100", "email": "",
              "site_url": "https://FILL.example", "demo_url": "", "status": "lead", "package": "", "setup_usd": 0, "monthly_usd": 0, "notes": "",
              "chat": dict({"preset": preset}, **sample, booking_url="", address="", maps_url="", facts={}),
              "review": {"google_review_url": "FILL: https://g.page/r/.../review", "owner_name": ""}}
    path = path or os.path.join(K.ROOT, "data", "agency", "clients", cid + ".json")
    if os.path.exists(path):
        raise K.ClientError(f"{path} already exists")
    K.write(path, json.dumps(client, indent=2, ensure_ascii=False) + "\n")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build a client's Front-desk chat widget.")
    ap.add_argument("client", nargs="?", help="the client file (JSON)")
    ap.add_argument("--out", help="output folder (default data/agency/upsells/<id>/)")
    ap.add_argument("--site", help="also install into this site folder (copies the JS, adds the 2 lines to every page)")
    ap.add_argument("--new", nargs=3, metavar=("PRESET", "ID", "NAME"), help="write a starter client file from a preset")
    a = ap.parse_args(argv)
    try:
        if a.new:
            print("starter client file:", new_client(*a.new), "(fill the FILL parts, then run this again with that file)")
            return 0
        if not a.client:
            ap.error("give the client file")
        build(a.client, a.out, a.site)
        return 0
    except K.ClientError as e:
        print("can't build the chat:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
