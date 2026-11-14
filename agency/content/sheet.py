"""The contact sheet: the owner's working page for one client-month (contact_sheet.html, offline, phone and desktop) and the
compact preview picture the client approves (contact_sheet.png).

The working page: the month at a glance (calendar), the questions to ask the client first, then every post with its square and
story image, date and time, caption, hashtags, a Copy caption button and a Scheduled tick box (ticks are remembered in this
browser only). Everything is inside the file except the images, which sit next to it in posts/.
"""
from __future__ import annotations

import calendar
import datetime as dt
import html
import json
import math

from agency.content import designs as D

KIND_COLOR = {"holiday": "#C2410C", "tip": "#0F766E", "service": "#1D4ED8", "offer": "#B45309", "season": "#0369A1", "bts": "#7C3AED",
              "team": "#7C3AED", "review": "#A16207", "faq": "#0E7490", "local": "#15803D", "engage": "#BE185D", "booking": "#4338CA",
              "checklist": "#047857"}
KIND_NAME = {"holiday": "Holiday", "tip": "Tip", "service": "Service", "offer": "Offer", "season": "Season", "bts": "Behind the scenes",
             "team": "Team", "review": "Reviews", "faq": "FAQ", "local": "Local", "engage": "Conversation", "booking": "Book ahead",
             "checklist": "Checklist"}


def esc(t) -> str:
    return html.escape(str(t or ""), quote=True)


def _when(p: dict) -> str:
    d = dt.date.fromisoformat(p["date"])
    h, m = (int(x) for x in p["time"].split(":"))
    return f"{d.strftime('%a')}, {d.strftime('%b')} {d.day} &middot; {(h % 12) or 12}:{m:02d} {'am' if h < 12 else 'pm'}"


def _fonts(brand: dict) -> str:
    return D.font_faces({"manrope", brand["fonts"]["display"], brand["fonts"]["accent"]})


def _calendar(plan: dict) -> str:
    y, m = (int(x) for x in plan["month"].split("-"))
    by_day = {int(p["date"][8:10]): p for p in plan["posts"]}
    cells = ['<div class="dow">' + d + "</div>" for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")]
    first, ndays = calendar.monthrange(y, m)
    cells += ['<div class="day empty"></div>'] * first
    for d in range(1, ndays + 1):
        p = by_day.get(d)
        if p:
            cells.append(f'<a class="day on" href="#p{p["n"]:02d}" style="--k:{KIND_COLOR.get(p["kind"], "#555")}" title="{esc(KIND_NAME.get(p["kind"], ""))}">'
                         f'<span class="dn">{d}</span><span class="dot"></span><span class="pn">#{p["n"]:02d}</span></a>')
        else:
            cells.append(f'<div class="day"><span class="dn">{d}</span></div>')
    return '<div class="cal">' + "".join(cells) + "</div>"


CSS = """
:root{--bg:#F5F3EE;--card:#FFFFFF;--ink:#1D2327;--ink2:#4B5563;--ink3:#6B7280;--line:#E4E0D8;--acc:%(acc)s;--hero:%(hero)s;--heroink:%(heroink)s;
--heroacc:%(heroacc)s;--fd:"%(fd)s";--fdw:%(fdw)s;--fds:%(fds)s}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15181B;--card:#1E2226;--ink:#ECEAE4;--ink2:#C3C0B8;--ink3:#9A978F;--line:#30353A}}
:root[data-theme=dark]{--bg:#15181B;--card:#1E2226;--ink:#ECEAE4;--ink2:#C3C0B8;--ink3:#9A978F;--line:#30353A}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%%}
body{margin:0;background:var(--bg);color:var(--ink);font:500 15px/1.5 "Manrope",system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}
a{color:inherit}
.hero{background:var(--hero);color:var(--heroink);position:relative;overflow:hidden}
.hero .pat{position:absolute;inset:0;background:%(pattern)s;opacity:.5;-webkit-mask:linear-gradient(100deg,transparent 35%%,#000);mask:linear-gradient(100deg,transparent 35%%,#000)}
.hero .in{position:relative;max-width:1180px;margin:0 auto;padding:34px 16px 30px}
.kick{font:800 12px/1 "Manrope";letter-spacing:.2em;text-transform:uppercase;color:var(--heroacc)}
h1{margin:12px 0 4px;font-family:var(--fd),Georgia,serif;font-weight:var(--fdw);font-style:var(--fds);font-size:clamp(34px,7vw,64px);line-height:1;letter-spacing:%(ls)s;%(tt)s}
.month{font:700 18px/1.3 "Manrope";opacity:.9}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin-top:20px}
.stat{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.18);border-radius:999px;padding:7px 14px;font:700 13px/1.2 "Manrope"}
.stat b{font-weight:800;color:var(--heroacc)}
main{max-width:1180px;margin:0 auto;padding:22px 16px 60px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:16px}
.panel h2{margin:0 0 12px;font:800 13px/1.2 "Manrope";letter-spacing:.16em;text-transform:uppercase;color:var(--ink3)}
.top{display:grid;gap:16px;grid-template-columns:1fr}
@media (min-width:900px){.top{grid-template-columns:1.1fr 1fr}}
ol.steps{margin:0;padding-left:20px;display:grid;gap:8px;color:var(--ink2)}ol.steps b{color:var(--ink)}
.cal{display:grid;grid-template-columns:repeat(7,1fr);gap:5px}
.cal .dow{font:800 10px/1 "Manrope";letter-spacing:.12em;text-transform:uppercase;color:var(--ink3);text-align:center;padding-bottom:4px}
.cal .day{position:relative;min-height:46px;border-radius:9px;background:var(--bg);padding:5px 6px;text-decoration:none}
.cal .day.empty{background:transparent}
.cal .dn{font:700 12px/1 "Manrope";color:var(--ink3)}
.cal .on{background:color-mix(in srgb,var(--k) 14%%,var(--card));outline:1.5px solid color-mix(in srgb,var(--k) 55%%,transparent)}
.cal .on .dn{color:var(--ink)}
.cal .dot{position:absolute;right:6px;top:6px;width:8px;height:8px;border-radius:50%%;background:var(--k)}
.cal .pn{position:absolute;left:6px;bottom:5px;font:800 10px/1 "Manrope";color:var(--k)}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;margin-top:12px;font:700 12px/1.2 "Manrope";color:var(--ink2)}
.legend i{display:inline-block;width:9px;height:9px;border-radius:50%%;margin-right:6px;vertical-align:0}
.checks li{margin:4px 0}.checks{margin:0;padding-left:20px;color:var(--ink2)}
.note{font-size:13px;color:var(--ink3);margin:10px 0 0}
.grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(290px,1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden;display:flex;flex-direction:column;scroll-margin-top:12px}
.card.done{opacity:.55}
.media{position:relative;display:grid;grid-template-columns:3fr 1fr;gap:6px;padding:8px;background:var(--bg)}
.media img{width:100%%;display:block;border-radius:9px;background:#ddd}
.media .sq{aspect-ratio:1/1;object-fit:cover}
.media .st{aspect-ratio:9/16;object-fit:cover;align-self:end}
.ph{aspect-ratio:1/1;border-radius:9px;background:var(--hero);color:var(--heroink);display:flex;align-items:center;justify-content:center;text-align:center;padding:18px;font:800 18px/1.25 "Manrope"}
.body{padding:14px 16px 16px;display:flex;flex-direction:column;gap:10px;flex:1}
.meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.no{font:800 12px/1 "Manrope";color:#fff;background:var(--k);border-radius:7px;padding:5px 7px}
.when{font:800 14px/1.2 "Manrope"}
.kind{margin-left:auto;font:800 10px/1 "Manrope";letter-spacing:.14em;text-transform:uppercase;color:var(--k)}
.cap{margin:0;white-space:pre-wrap;color:var(--ink);font-size:14px;line-height:1.55;max-height:12.5em;overflow:auto}
.tags{margin:0;font-size:13px;color:var(--acc);word-break:break-word}
.flag{font-size:13px;line-height:1.4;border-radius:10px;padding:8px 10px}
.flag.q{background:color-mix(in srgb,#F59E0B 16%%,var(--card));border:1px solid color-mix(in srgb,#F59E0B 45%%,transparent)}
.flag.pi{background:color-mix(in srgb,#7C3AED 10%%,var(--card));border:1px solid color-mix(in srgb,#7C3AED 35%%,transparent);color:var(--ink2)}
.act{display:flex;gap:10px;align-items:center;margin-top:auto;padding-top:4px}
button.copy{appearance:none;border:0;border-radius:10px;background:var(--ink);color:var(--card);font:800 14px/1 "Manrope";padding:0 16px;min-height:44px;cursor:pointer}
button.copy.ok{background:#15803D;color:#fff}
label.tick{display:flex;align-items:center;gap:8px;font:700 14px/1 "Manrope";color:var(--ink2);min-height:44px;cursor:pointer}
label.tick input{width:20px;height:20px;accent-color:#15803D}
.dl{font:700 13px/1 "Manrope";color:var(--ink3);margin-left:auto;text-decoration:none;min-height:44px;display:flex;align-items:center}
footer{max-width:1180px;margin:0 auto;padding:0 16px 40px;color:var(--ink3);font-size:13px}
:focus-visible{outline:3px solid var(--acc);outline-offset:2px}
@media print{.act,.dl{display:none}.card{break-inside:avoid}}
"""

JS = r"""(function(){
var KEY='agency-sheet:'+document.body.getAttribute('data-key');
function load(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){return {}}}
function save(s){try{localStorage.setItem(KEY,JSON.stringify(s))}catch(e){}}
var st=load();
document.querySelectorAll('label.tick input').forEach(function(cb){var id=cb.getAttribute('data-id');cb.checked=!!st[id];
 cb.closest('.card').classList.toggle('done',cb.checked);
 cb.addEventListener('change',function(){st[id]=cb.checked;save(st);cb.closest('.card').classList.toggle('done',cb.checked);});});
function fallback(t){var a=document.createElement('textarea');a.value=t;a.setAttribute('readonly','');a.style.position='fixed';a.style.opacity='0';
 document.body.appendChild(a);a.select();var ok=false;try{ok=document.execCommand('copy')}catch(e){}document.body.removeChild(a);return ok;}
document.querySelectorAll('button.copy').forEach(function(b){b.addEventListener('click',function(){
 var t=document.getElementById(b.getAttribute('data-src')).value;function done(){b.textContent='Copied';b.classList.add('ok');
 setTimeout(function(){b.textContent='Copy caption';b.classList.remove('ok')},1600);}
 if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(t).then(done,function(){if(fallback(t))done();});}
 else if(fallback(t)){done();}});});
document.documentElement.setAttribute('data-ready','1');})();"""


def _css(plan: dict, brand: dict) -> str:
    v = brand["vars"]
    fd = D.FONTS[brand["fonts"]["display"]]
    up = fd[6] == "upper"
    return CSS % {"acc": v["acc_p"], "hero": v["bg"], "heroink": v["ink"], "heroacc": v["acc_d"], "fd": fd[0], "fdw": fd[2], "fds": fd[3],
                  "pattern": D.trade_pattern(brand["motif"], v["line_d"], 1), "ls": ".01em" if up else "-.015em",
                  "tt": "text-transform:uppercase;" if up else ""}


def contact_sheet(plan: dict, brand: dict) -> str:
    posts = plan["posts"]
    n = len(posts)
    kinds = []
    for p in posts:
        if p["kind"] not in kinds:
            kinds.append(p["kind"])
    legend = "".join(f'<span><i style="background:{KIND_COLOR.get(k, "#555")}"></i>{esc(KIND_NAME.get(k, k))}</span>' for k in kinds)
    checks = ""
    if plan["checks"]:
        checks = ('<section class="panel" aria-labelledby="qh"><h2 id="qh">Ask the client first</h2><ol class="checks">'
                  + "".join(f"<li>{esc(q)}</li>" for q in plan["checks"])
                  + '</ol><p class="note">These questions are in client_message.txt, ready to send with contact_sheet.png.</p></section>')
    cards = []
    for p in posts:
        k = KIND_COLOR.get(p["kind"], "#555")
        full = p["caption"] + "\n\n" + " ".join(p["hashtags"])
        img = (f'<img class="sq" src="{esc(p["square"])}" alt="{esc(p["alt"])}" loading="lazy" width="1080" height="1080">'
               f'<a href="{esc(p["story"])}" title="Story image"><img class="st" src="{esc(p["story"])}" alt="Story version" loading="lazy" width="1080" height="1920"></a>')
        flags = ""
        if p["check"]:
            flags += f'<div class="flag q"><b>Check first:</b> {esc(p["check"])}</div>'
        if p["photo_idea"]:
            flags += f'<div class="flag pi">{esc(p["photo_idea"])}</div>'
        cards.append(
            f'<article class="card" id="p{p["n"]:02d}" style="--k:{k}"><div class="media">{img}</div><div class="body">'
            f'<div class="meta"><span class="no">#{p["n"]:02d}</span><span class="when">{_when(p)}</span><span class="kind">{esc(KIND_NAME.get(p["kind"], p["kind"]))}</span></div>'
            f'<p class="cap">{esc(p["caption"])}</p><p class="tags">{esc(" ".join(p["hashtags"]))}</p>{flags}'
            f'<textarea id="c{p["n"]:02d}" hidden>{esc(full)}</textarea>'
            f'<div class="act"><button class="copy" type="button" data-src="c{p["n"]:02d}">Copy caption</button>'
            f'<label class="tick"><input type="checkbox" data-id="{p["n"]}"> Scheduled</label>'
            f'<a class="dl" href="{esc(p["square"])}" download>Image</a></div></div></article>')
    b = plan["brand"]
    title = f"{b['name']} - {plan['label']} posts"
    key = f"{plan['client'].get('id') or b['name']}:{plan['month']}"
    hero = (f'<header class="hero"><div class="pat"></div><div class="in"><div class="kick">Social plan &middot; {esc(plan["trade_label"])}'
            f'{" &middot; " + esc(b["city"]) if b.get("city") else ""}</div><h1>{esc(b["name"])}</h1><div class="month">{esc(plan["label"])}</div>'
            f'<div class="stats"><span class="stat"><b>{n}</b> posts</span><span class="stat"><b>{n}</b> stories</span>'
            f'<span class="stat">about <b>{max(1, round(n / (S_weeks(plan))))}</b> a week</span>'
            f'<span class="stat"><b>{len(plan["checks"])}</b> questions for the client</span></div></div></header>')
    steps = ('<section class="panel" aria-labelledby="hh"><h2 id="hh">How to post</h2><ol class="steps">'
             '<li><b>Get the OK.</b> Send <i>client_message.txt</i> and <i>contact_sheet.png</i> to the client.</li>'
             '<li><b>Schedule in Meta Business Suite</b> (business.facebook.com &rsaquo; Planner): click the day, Schedule post, add the square '
             'image, tap <b>Copy caption</b> here and paste, tick Facebook + Instagram, set the time shown. Stories: Create story, same day.</li>'
             '<li><b>Tick Scheduled</b> on each card as you go. Schedule on the 1st: Meta plans about a month ahead.</li></ol>'
             f'<p class="note">Best times for this trade: {esc(plan["times_note"])}. After a month, check Insights and move toward the hours that got the most reach.</p></section>')
    cal = (f'<section class="panel" aria-labelledby="ch"><h2 id="ch">{esc(plan["label"])} at a glance</h2>{_calendar(plan)}'
           f'<div class="legend">{legend}</div></section>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><style>{_fonts(brand)}{_css(plan, brand)}</style></head>'
            f'<body data-key="{esc(key)}">{hero}<main><div class="top">{steps}{cal}</div>{checks}'
            f'<h2 class="sr" style="position:absolute;left:-9999px">Posts</h2><section class="grid" aria-label="Posts">{"".join(cards)}</section></main>'
            f'<footer>Made {esc(plan["generated"][:10])} by the agency content machine. Images: posts/ (square 1080 x 1080, story 1080 x 1920). '
            f'Schedule sheet: posts.csv.</footer><script>{JS}</script></body></html>')


def S_weeks(plan: dict) -> float:
    y, m = (int(x) for x in plan["month"].split("-"))
    return calendar.monthrange(y, m)[1] / 7.0


PREVIEW_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1600px;background:%(paper)s}
body{font:500 18px/1.4 "Manrope",sans-serif;color:%(pink)s;-webkit-font-smoothing:antialiased}
.hd{background:%(bg)s;color:%(ink)s;padding:54px 64px 46px;position:relative;overflow:hidden}
.hd .pat{position:absolute;inset:0;background:%(pattern)s;opacity:.5;-webkit-mask:linear-gradient(100deg,transparent 40%%,#000);mask:linear-gradient(100deg,transparent 40%%,#000)}
.hd .in{position:relative;display:flex;align-items:flex-end;justify-content:space-between;gap:40px}
.kick{font:800 16px/1 "Manrope";letter-spacing:.22em;text-transform:uppercase;color:%(accd)s}
.nm{font-family:"%(fd)s",serif;font-weight:%(fdw)s;font-style:%(fds)s;font-size:84px;line-height:1;margin-top:16px;letter-spacing:%(ls)s;%(tt)s}
.mo{font:700 24px/1.3 "Manrope";margin-top:10px;opacity:.9}
.chips{display:flex;gap:10px}
.chip{border:1.5px solid %(lined)s;border-radius:999px;padding:10px 20px;font:800 18px/1 "Manrope";white-space:nowrap}
.chip b{color:%(accd)s}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:28px;padding:44px 64px 30px}
.it img{width:100%%;aspect-ratio:1/1;display:block;border-radius:14px;box-shadow:0 18px 30px -18px rgba(0,0,0,.35)}
.cap{display:flex;gap:10px;align-items:baseline;margin-top:12px;font:800 17px/1.2 "Manrope"}
.cap .n{color:%(accp)s}.cap .k{margin-left:auto;font:700 13px/1 "Manrope";letter-spacing:.14em;text-transform:uppercase;opacity:.65}
.ft{padding:6px 64px 46px;font:600 16px/1.4 "Manrope";opacity:.7}
"""


def preview_page(plan: dict, brand: dict) -> str:
    v = brand["vars"]
    fd = D.FONTS[brand["fonts"]["display"]]
    up = fd[6] == "upper"
    css = PREVIEW_CSS % {"paper": v["paper"], "pink": v["paper_ink"], "bg": v["bg"], "ink": v["ink"], "accd": v["acc_d"], "accp": v["acc_p"],
                         "lined": v["line_d"], "fd": fd[0], "fdw": fd[2], "fds": fd[3], "pattern": D.trade_pattern(brand["motif"], v["line_d"], 1),
                         "ls": ".01em" if up else "-.015em", "tt": "text-transform:uppercase;" if up else ""}
    items = []
    for p in plan["posts"]:
        d = dt.date.fromisoformat(p["date"])
        items.append(f'<div class="it"><img src="{esc(p["square"])}" alt=""><div class="cap"><span class="n">#{p["n"]:02d}</span>'
                     f'<span>{d.strftime("%a %b")} {d.day}</span><span class="k">{esc(KIND_NAME.get(p["kind"], p["kind"]))}</span></div></div>')
    b = plan["brand"]
    n = len(plan["posts"])
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{_fonts(brand)}{css}</style></head><body>'
            f'<div class="hd"><div class="pat"></div><div class="in"><div><div class="kick">{esc(plan["trade_label"])} social plan</div>'
            f'<div class="nm">{esc(b["name"])}</div><div class="mo">{esc(plan["label"])}{" &middot; " + esc(b["city"]) if b.get("city") else ""}</div></div>'
            f'<div class="chips"><span class="chip"><b>{n}</b> posts</span><span class="chip"><b>{n}</b> stories</span></div></div></div>'
            f'<div class="grid">{"".join(items)}</div><div class="ft">Each post also has a 9:16 story version. Reply YES to schedule.</div>'
            '<script>(function(){var im=[].slice.call(document.images),n=im.length;function d(){if(--n<=0)document.documentElement.setAttribute("data-ready","1")}'
            'if(!n){document.documentElement.setAttribute("data-ready","1")}im.forEach(function(i){if(i.complete)d();else{i.onload=d;i.onerror=d}});})();</script>'
            '</body></html>')


def preview_height(plan: dict) -> int:
    return 230 + math.ceil(len(plan["posts"]) / 4) * 410 + 110
