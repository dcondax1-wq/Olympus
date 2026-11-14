"""CONTENT PLAN: a 30-day Instagram plan per account: dated posts, captions, hashtags, alt text and a designed image for each.

    python -m money_machines.content_plan --account local_growth                  # write plans/local_growth_30d.json + .md (start: next Monday)
    python -m money_machines.content_plan --account eval_journal --start 2026-11-16
    python -m money_machines.content_plan --account local_growth --render         # + 30 JPEG images (1080 x 1350) and a posting sheet
    python -m money_machines.content_plan --all --render                          # both accounts
    python -m money_machines.content_plan --check                                 # the committed plans are valid and up to date

Images: one HTML card per post, rendered to JPEG by the pre-installed Chromium (playwright). Instagram's publishing API takes
JPEG only, 4:5 portrait fits its 4:5-1.91:1 range. Out: money_machines/out/content/<account>/dayNN.jpg + index.html (the posting
sheet: image + caption + date, to schedule by hand in Meta Business Suite, free). The look is OLYMPUS AGORA (ivory and night,
gold and olive, serif titles). When the agency content kit (team B5, agency/content/designs.py) is installed, the cards use
its embedded open fonts (Fraunces titles, Manrope text) like the agency's own posts; --style FILE overrides colours and fonts.

Nothing here posts. Posting is money_machines/ig_post.py (dry run by default) or the owner in Meta Business Suite.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import html
import json
import os
import re
import sys

from money_machines import content_topics as T

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLANS = os.path.join(HERE, "plans")
OUT = os.environ.get("MONEY_MACHINES_OUT") or os.path.join(HERE, "out")
DAYS = 30
FIXED_START = "2026-11-16"            # the committed plans start here (a Monday); --start changes it
CAPTION_MAX = 2200                    # Instagram caption limit
HASHTAG_MAX = 5                       # Instagram limits posts to 5 hashtags since Dec 2025 (reports differ: 5 is safe either way)

STYLES = {
    "local_growth": {"bg": "#f3ece0", "panel": "#fbf7ef", "ink": "#14110e", "soft": "#4a4238", "accent": "#7d5f25", "accent2": "#5e6a33",
                     "chip_bg": "#e9dfcb", "line": "#d8ccb5", "serif": "'Iowan Old Style','Palatino Linotype',Palatino,Caladea,Georgia,serif",
                     "sans": "-apple-system,'Segoe UI',Inter,system-ui,sans-serif"},
    "eval_journal": {"bg": "#14110e", "panel": "#1d1914", "ink": "#f3ece0", "soft": "#cfc4b2", "accent": "#c8a24a", "accent2": "#a9b57a",
                     "chip_bg": "#26211b", "line": "#3a3228", "serif": "'Iowan Old Style','Palatino Linotype',Palatino,Caladea,Georgia,serif",
                     "sans": "-apple-system,'Segoe UI',Inter,system-ui,sans-serif"},
}

# performance and income claims the eval journal must never make (checked on every caption and image text)
CLAIMS = [r"\b(?:i|we)\s+(?:made|earned|profited|banked|passed|cashed)\b", r"\bguarantee", r"\brisk[- ]free\b", r"\bpassive income\b",
          r"\beasy money\b", r"\bfree money\b", r"\bcopy (?:my|our) trades\b", r"\bget funded fast\b", r"\b\d+\s?% (?:return|gain|profit|win rate)",
          r"\bwin rate of\b", r"\bsignal(?:s)? (?:group|service|alert)", r"\bpayout (?:proof|screenshot)", r"\$\s?\d[\d,.]*\s*(?:a|per)\s*(?:day|week|month)",
          r"\bmillionaire\b", r"\bquit (?:your|my) job\b", r"\bfinancial freedom\b"]
LOCAL_CLAIMS = [r"\bguarantee", r"#1 on google", r"\brank (?:you )?first\b", r"\btop of google\b", r"\bmore customers in \d+ days\b",
                r"\b(?:discount|free \w+|gift card) (?:for|in exchange for) (?:a |your )?(?:5[- ]star )?review"]


# words that mean money changes hands for the post or the link; such a caption must START with a clear label (FTC: before "more")
PAID = r"(?:affiliate|sponsor|(?:earn|get|receive)s? a commission|promo code|discount code|use (?:my )?code|paid partnership|#ad\b|\b\d+% off\b)"


def disclosed_first(caption: str) -> bool:
    first = caption.split("\n", 1)[0].strip().lower()
    return bool(re.match(r"(?:#ad\b|ad\b|ad:|ad ·|sponsored\b|paid partnership\b)", first)
                or (first.startswith("affiliate link") and "commission" in first))


def next_monday(today: dt.date | None = None) -> dt.date:
    t = today or dt.date.today()
    return t + dt.timedelta(days=(7 - t.weekday()) % 7 or 7)


def build_plan(account: str, start: dt.date, days: int = DAYS) -> dict:
    meta = T.ACCOUNTS[account]
    regular, specials = T.TOPICS[account]
    if len(regular) < days:
        raise ValueError(f"{account}: needs at least {days} regular topics, has {len(regular)}")
    sdates = {}
    for y in {start.year, (start + dt.timedelta(days=days)).year}:
        for rule, d in T.special_dates(y).items():
            sdates.setdefault(d, rule)
    by_rule = {s["rule"]: s for s in specials}
    posts, ri = [], 0
    for i in range(days):
        d = start + dt.timedelta(days=i)
        rule = sdates.get(d)
        if rule in by_rule:
            topic, special = by_rule[rule], rule
        else:
            topic, special = regular[ri], ""
            ri += 1
        posts.append(make_post(account, meta, topic, i + 1, d, special))
    return {"v": 1, "kind": "ig-content-plan", "account": account, "title": meta["title"], "bio": meta["bio"], "handle_ideas": meta["handle_ideas"],
            "purpose": meta["purpose"], "start": start.isoformat(), "days": days, "tz": "America/New_York", "posts": posts,
            "rules": rules_for(account)}


def rules_for(account: str) -> list:
    base = ["Post from the owner's own account; schedule in Meta Business Suite (free) or ig_post.py with his own token.",
            f"At most {HASHTAG_MAX} hashtags; captions under {CAPTION_MAX} characters; alt text on every image.",
            "No bought followers, likes or comments; no follow/unfollow or auto-DM tools (Instagram bans automated engagement)."]
    if account == "eval_journal":
        base += ["Education only. Never show or claim results, profits, income, passes or payouts; no signals; no 'copy my trades'.",
                 "Every caption ends with the risk line. Numbers appear only in posts labelled 'Example only'.",
                 "A paid or affiliate link: start the caption with 'Ad' or 'Affiliate link' before anything else (FTC: disclose before 'more').",
                 "Own product: say it is your own product in the caption."]
    else:
        base += ["Never promise rankings; examples are labelled as examples; no fake reviews or review tricks.",
                 "Interested owners go to the free website check (agency storefront), not to cold DMs."]
    return base


def make_post(account: str, meta: dict, topic: dict, n: int, d: dt.date, special: str) -> dict:
    ctas = meta["ctas"]
    cta = ctas[(n - 1) % len(ctas)]
    tags = meta["hashtags"][(n - 1) % len(meta["hashtags"])][:HASHTAG_MAX]
    lines = [topic["headline"], "", topic["body"], ""]
    lines += [f"{i}. {p}" for i, p in enumerate(topic["points"], 1)]
    lines += ["", cta, "", " ".join(tags)]
    if meta["risk_line"]:
        lines += ["", meta["risk_line"]]
    caption = "\n".join(lines)
    alt = f"Text card from {meta['title']}: {topic['headline']}. " + "; ".join(topic["points"]) + "."
    return {"day": n, "date": d.isoformat(), "weekday": d.strftime("%a"), "time": meta["time"], "pillar": topic["pillar"],
            "special": special, "example": bool(topic.get("example")), "headline": topic["headline"], "points": topic["points"],
            "caption": caption, "hashtags": tags, "alt_text": alt, "image": f"{account}/day{n:02d}.jpg", "format": "image 1080x1350 (4:5)"}


def validate(plan: dict) -> list:
    """Problems as plain lines; [] = the plan is fit to post."""
    p = []
    posts = plan["posts"]
    if len(posts) != plan["days"]:
        p.append(f"{len(posts)} posts for {plan['days']} days")
    start = dt.date.fromisoformat(plan["start"])
    for i, x in enumerate(posts):
        if x["date"] != (start + dt.timedelta(days=i)).isoformat() or x["day"] != i + 1:
            p.append(f"day {i + 1}: date {x['date']} is not consecutive")
    caps = [x["caption"] for x in posts]
    if len(set(caps)) != len(caps) or len({x["headline"] for x in posts}) != len(posts):
        p.append("repeated caption or headline")
    claims = CLAIMS if plan["account"] == "eval_journal" else LOCAL_CLAIMS
    risk = T.ACCOUNTS[plan["account"]]["risk_line"]
    for x in posts:
        tag = f"day {x['day']}"
        if len(x["caption"]) > CAPTION_MAX:
            p.append(f"{tag}: caption {len(x['caption'])} chars")
        if len(x["hashtags"]) > HASHTAG_MAX or x["caption"].count("#") > HASHTAG_MAX or any(not re.fullmatch(r"#[a-z0-9_]+", h) for h in x["hashtags"]):
            p.append(f"{tag}: hashtags {x['hashtags']}")
        if not x["alt_text"] or len(x["headline"]) > 70 or not 2 <= len(x["points"]) <= 5 or max(len(q) for q in x["points"]) > 60:
            p.append(f"{tag}: alt text, headline (<= 70) or points (2-5, <= 60 chars) out of bounds")
        text = (x["caption"] + " " + " ".join(x["points"])).lower()
        for c in claims:
            if re.search(c, text):
                p.append(f"{tag}: claim pattern {c!r}")
        if risk and not x["caption"].rstrip().endswith(risk):
            p.append(f"{tag}: the risk line is missing")
        if plan["account"] == "eval_journal" and "$" in x["caption"] and "example only" not in x["caption"].lower():
            p.append(f"{tag}: a dollar amount outside an 'Example only' post")
        if re.search(PAID, text) and not disclosed_first(x["caption"]):
            p.append(f"{tag}: a paid link must be disclosed at the start of the caption")
    return p


# ------------------------------------------------------------------------------------------------ files
def plan_paths(account: str) -> tuple:
    return os.path.join(PLANS, f"{account}_30d.json"), os.path.join(PLANS, f"{account}_30d.md")


def plan_md(plan: dict) -> str:
    L = [f"# {plan['title']}: 30-day Instagram plan (from {plan['start']}, generated by `money_machines/content_plan.py`)", "",
         f"**What it is for:** {plan['purpose']}", "", f"**Bio:** {plan['bio']}", "",
         f"**Handle ideas (check they are free):** {', '.join(plan['handle_ideas'])}", "", "**Rules:**", ""] + [f"- {r}" for r in plan["rules"]]
    L += ["", "| Day | Date | Time ET | Pillar | Headline |", "|---|---|---|---|---|"]
    L += [f"| {x['day']} | {x['weekday']} {x['date']} | {x['time']} | {x['pillar']}{' (' + x['special'].replace('_', ' ') + ')' if x['special'] else ''} | {x['headline']} |"
          for x in plan["posts"]]
    L += [""]
    for x in plan["posts"]:
        L += [f"## Day {x['day']}: {x['weekday']} {x['date']} {x['time']}", "", "```", x["caption"], "```", "", f"Alt text: {x['alt_text']}", ""]
    return "\n".join(L)


def write_plan(plan: dict) -> tuple:
    os.makedirs(PLANS, exist_ok=True)
    jp, mp = plan_paths(plan["account"])
    with open(jp, "w", encoding="utf-8") as fh:
        json.dump(plan, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    with open(mp, "w", encoding="utf-8") as fh:
        fh.write(plan_md(plan))
    return jp, mp


# ------------------------------------------------------------------------------------------------ images
def b5_fonts() -> tuple:
    """Team B5's embedded OFL fonts (agency/content/designs.py: Fraunces titles, Manrope text) when the agency content kit is
    installed, so our cards share the agency posts' type; else ("", "", "") and the system font stacks are used."""
    try:
        from agency.content import designs as D
        return D.font_faces(["fraunces", "manrope"]), "'Fraunces',", "'Manrope',"
    except Exception:
        return "", "", ""


def load_style(account: str, style_file: str | None = None) -> dict:
    st = dict(STYLES[account])
    faces, serif, sans = b5_fonts()
    st.update(faces=faces, serif=serif + st["serif"], sans=sans + st["sans"])
    if style_file:
        try:
            with open(style_file, encoding="utf-8") as fh:
                ext = json.load(fh)
            ext = ext.get(account, ext) if isinstance(ext, dict) else {}
            st.update({k: v for k, v in ext.items() if k in st and isinstance(v, str) and (k in ("serif", "sans") or re.fullmatch(r"#[0-9a-fA-F]{6}", v))})
        except (OSError, ValueError):
            pass
    return st


def card_html(plan: dict, post: dict, style: dict) -> str:
    s = style
    head = post["headline"]
    hs = 92 if len(head) <= 28 else 82 if len(head) <= 40 else 72 if len(head) <= 52 else 64
    pts = "".join(f"<li><span class='tick'><svg viewBox='0 0 24 24' width='34' height='34'><path d='M5 12.5l4.2 4.2L19 7' fill='none' "
                  f"stroke='{s['accent2']}' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'/></svg></span>{html.escape(q)}</li>"
                  for q in post["points"])
    chip = html.escape(post["pillar"] + (" · Example" if post["example"] else ""))
    big = len(post["points"]) <= 3
    note = takeaway(post)
    foot_r = "Save for later" if plan["account"] == "local_growth" else "Education only · not financial advice"
    risk = ("<div class='risk'>Futures trading involves substantial risk of loss. No results are shown or promised.</div>"
            if plan["account"] == "eval_journal" else "")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{s.get('faces', '')}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:1080px;height:1350px;background:{s['bg']}}}
body{{font-family:{s['sans']};color:{s['ink']};padding:64px 72px;display:flex;flex-direction:column}}
.top{{display:flex;justify-content:space-between;align-items:center;font-size:30px;color:{s['soft']}}}
.brand{{font-family:{s['serif']};font-weight:700;color:{s['accent']};font-size:34px}}
.chip{{background:{s['chip_bg']};border:2px solid {s['line']};border-radius:999px;padding:10px 24px;font-size:28px;color:{s['soft']}}}
.card{{margin-top:56px;background:{s['panel']};border:2px solid {s['line']};border-radius:40px;padding:64px 64px 56px;flex:1;display:flex;flex-direction:column;
box-shadow:0 18px 40px rgba(0,0,0,.18)}}
h1{{font-family:{s['serif']};font-weight:700;font-size:{hs}px;line-height:1.08;letter-spacing:-.01em}}
.rule{{width:140px;height:8px;border-radius:4px;background:{s['accent']};margin:40px 0 44px}}
ul{{list-style:none;display:flex;flex-direction:column;gap:{36 if big else 28}px}}
li{{display:flex;gap:22px;align-items:flex-start;font-size:{46 if big else 41}px;line-height:1.22;color:{s['ink']}}}
.tick{{flex:0 0 52px;height:52px;border-radius:16px;background:{s['chip_bg']};display:flex;align-items:center;justify-content:center;margin-top:-2px}}
.note{{margin-top:auto;padding-top:36px;border-top:2px solid {s['line']};font-family:{s['serif']};font-style:italic;font-size:33px;line-height:1.32;color:{s['soft']}}}
.risk{{padding-top:20px;font-size:25px;color:{s['soft']};line-height:1.3}}
.foot{{display:flex;justify-content:space-between;align-items:center;margin-top:40px;font-size:28px;color:{s['soft']}}}
.n{{font-variant-numeric:tabular-nums}}
</style></head><body>
<div class="top"><span class="brand">{html.escape(plan['title'])}</span><span class="chip">{chip}</span></div>
<div class="card"><h1>{html.escape(head)}</h1><div class="rule"></div><ul>{pts}</ul><p class="note">{html.escape(note)}</p>{risk}</div>
<div class="foot"><span>{html.escape(plan['handle_ideas'][0])}</span><span>{foot_r} · <span class="n">{post['day']}/{plan['days']}</span></span></div>
</body></html>"""


def takeaway(post: dict, limit: int = 150) -> str:
    """The first sentence of the caption body, for the bottom of the card (cut at a word when long)."""
    parts = post["caption"].split("\n\n")
    body = parts[1] if len(parts) > 1 else post["headline"]
    first = re.split(r"(?<=[.!?])\s", body, maxsplit=1)[0]
    if len(first) <= limit:
        return first
    return first[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def chromium_path():
    return next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)


def render(plan: dict, out: str | None = None, only=None, style_file: str | None = None, quality: int = 86) -> list:
    """JPEG per post (1080 x 1350) + index.html (posting sheet). Returns the image paths; [] if playwright is missing."""
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("no images: playwright is not installed (pip install playwright, then python -m playwright install chromium)")
        return []
    out = out or os.path.join(OUT, "content")
    style = load_style(plan["account"], style_file)
    os.makedirs(os.path.join(out, plan["account"]), exist_ok=True)
    done = []
    exe = chromium_path()
    with sync_playwright() as pw:
        br = pw.chromium.launch(args=["--no-sandbox"], **({"executable_path": exe} if exe else {}))
        pg = br.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        for post in plan["posts"]:
            if only and post["day"] not in only:
                continue
            pg.set_content(card_html(plan, post, style))
            path = os.path.join(out, post["image"])
            pg.screenshot(path=path, type="jpeg", quality=quality, clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
            done.append(path)
        br.close()
    write_sheet(plan, out)
    return done


def write_sheet(plan: dict, out: str) -> str:
    rows = "".join(f"<section><h2>Day {x['day']} &middot; {x['weekday']} {x['date']} &middot; {x['time']} ET</h2>"
                   f"<img src='{html.escape(os.path.basename(x['image']))}' alt='{html.escape(x['alt_text'])}' loading='lazy'>"
                   f"<pre>{html.escape(x['caption'])}</pre><p class='alt'>Alt text: {html.escape(x['alt_text'])}</p></section>" for x in plan["posts"])
    page = ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(plan['title'])} posting sheet</title><style>body{{margin:0;background:#f4f1ea;color:#1c1a17;"
            "font-family:-apple-system,'Segoe UI',system-ui,sans-serif}main{max-width:720px;margin:0 auto;padding:16px}"
            "section{background:#fff;border-radius:16px;padding:14px;margin:14px 0;box-shadow:0 2px 8px rgba(0,0,0,.08)}"
            "img{width:100%;height:auto;border-radius:10px}pre{white-space:pre-wrap;font-family:inherit;font-size:15px}"
            "h2{font-family:Georgia,serif;font-size:18px}.alt{color:#6b6256;font-size:13px}</style></head><body><main>"
            f"<h1>{html.escape(plan['title'])}</h1><p>Schedule each post in Meta Business Suite &gt; Planner: upload the image, paste the caption, "
            f"add the alt text (Advanced settings), pick the date and time.</p>{rows}</main></body></html>\n")
    path = os.path.join(out, plan["account"], "index.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    csv_path = os.path.join(out, plan["account"], "schedule.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["day", "date", "time_et", "image", "caption", "alt_text"])
        for x in plan["posts"]:
            w.writerow([x["day"], x["date"], x["time"], os.path.basename(x["image"]), x["caption"], x["alt_text"]])
    return path


# ------------------------------------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m money_machines.content_plan", description="30-day Instagram plan + images.")
    ap.add_argument("--account", choices=sorted(T.ACCOUNTS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--start", help="YYYY-MM-DD (default: the committed start, or next Monday with --fresh)")
    ap.add_argument("--fresh", action="store_true", help="start next Monday instead of the committed date")
    ap.add_argument("--render", action="store_true", help="also make the JPEG images and the posting sheet")
    ap.add_argument("--days", help="render only these days, e.g. 1,2,3")
    ap.add_argument("--out", help="image folder (default money_machines/out/content)")
    ap.add_argument("--style", help="a style JSON (colours/fonts) to use for the images")
    ap.add_argument("--check", action="store_true", help="the committed plans are valid and equal a fresh build")
    a = ap.parse_args(argv)
    accounts = sorted(T.ACCOUNTS) if (a.all or a.check or not a.account) else [a.account]
    rc = 0
    for acc in accounts:
        start = dt.date.fromisoformat(a.start) if a.start else (next_monday() if a.fresh else dt.date.fromisoformat(FIXED_START))
        plan = build_plan(acc, start)
        probs = validate(plan)
        if probs:
            rc = 1
            print(f"{acc}: " + "; ".join(probs))
        if a.check:
            jp, _ = plan_paths(acc)
            same = os.path.exists(jp) and json.load(open(jp, encoding="utf-8")) == json.loads(json.dumps(plan))
            print(f"{acc}: {'OK' if same and not probs else 'STALE or invalid: run python -m money_machines.content_plan --all'}")
            rc = rc or (0 if same else 1)
            continue
        jp, mp = write_plan(plan)
        print(f"{acc}: {len(plan['posts'])} posts from {plan['start']} -> {os.path.relpath(jp, ROOT)}, {os.path.relpath(mp, ROOT)}"
              + ("" if not probs else "  (NOT VALID, see above)"))
        if a.render:
            only = {int(x) for x in a.days.split(",")} if a.days else None
            imgs = render(plan, a.out, only, a.style)
            if imgs:
                print(f"  {len(imgs)} images + posting sheet in {os.path.dirname(imgs[0])}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
