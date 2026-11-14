"""SELF-CHECK: a Lighthouse-style test of a built site folder, stdlib only (no browser needed).

    python -m agency.sitecheck agency/out/sites/<slug>/site          prints the four scores and what to fix

Four scores 0-100 like Lighthouse (performance, accessibility, best practices, SEO) from checks that can be proven from
the files alone: valid HTML (every tag closed, ids unique), no file loaded from another site (no hotlinked photo, font,
script or stylesheet), the size budget, the phone viewport, colour contrast measured with the WCAG formula on the theme's
own colours, labels on every form field, one h1, heading order, alt text / hidden decoration, tap-target rules, title and
description lengths, structured data that parses, the security headers file. A HARD FAIL (ok = False) is something a
client must never receive: a hotlink, broken HTML, no viewport, unreadable text, an unlabelled field, a missing h1.
"""
from __future__ import annotations

import html.parser
import json
import os
import re
import sys

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
RESOURCE_ATTRS = {("link", "href"), ("script", "src"), ("img", "src"), ("img", "srcset"), ("source", "src"), ("source", "srcset"), ("video", "src"),
                  ("video", "poster"), ("audio", "src"), ("iframe", "src"), ("embed", "src"), ("object", "data"), ("image", "href"), ("image", "xlink:href"),
                  ("use", "href"), ("use", "xlink:href"), ("input", "src")}
NOT_LOADED = {"canonical", "alternate", "author", "license", "me", "next", "prev", "help", "search"}
BUDGET_PAGE, HARD_PAGE, BUDGET_TOTAL = 60_000, 120_000, 200_000


def luminance(hexcolor: str) -> float:
    h = hexcolor.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def external(url: str) -> bool:
    u = (url or "").strip().lower()
    return u.startswith(("http://", "https://", "//")) or (":" in u.split("/")[0] and not u.startswith(("data:", "#", "mailto:", "tel:")))


class Page(html.parser.HTMLParser):
    """Collects what the checks need in one pass; records structural errors instead of raising."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.ids, self.dupe_ids = [], [], set(), []
        self.tags, self.resources, self.links, self.forms, self.controls, self.labels_for, self.wrapped = [], [], [], [], [], set(), set()
        self.headings, self.title, self.meta, self.html_lang, self.svgs, self.scripts, self.styles, self.inline_handlers = [], "", {}, "", [], [], [], []
        self._in, self._text, self._label_depth, self._a = None, [], 0, None
        self.doctype = False

    def handle_decl(self, decl):
        self.doctype = self.doctype or decl.lower().startswith("doctype html")

    def _attrs(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        if "id" in a:
            (self.dupe_ids.append(a["id"]) if a["id"] in self.ids else self.ids.add(a["id"]))
        for k, v in a.items():
            if k.startswith("on"):
                self.inline_handlers.append(f"{tag} {k}")
            if (tag, k) in RESOURCE_ATTRS and v:
                if tag == "link" and set(a.get("rel", "").lower().split()) & NOT_LOADED:
                    continue                                # rel=canonical / alternate name a page, they load nothing
                for part in re.split(r",\s*", v) if k == "srcset" else [v]:
                    self.resources.append((tag, k, part.split()[0] if part.split() else part))
            if k == "style" and re.search(r"url\(", v):
                self.styles.append(v)
        return a

    def handle_starttag(self, tag, attrs):
        a = self._attrs(tag, attrs)
        self.tags.append((tag, a))
        if tag == "html":
            self.html_lang = a.get("lang", "")
        elif tag == "meta":
            key = a.get("name") or a.get("property") or ("charset" if "charset" in a else "")
            if key:
                self.meta[key.lower()] = a.get("content", a.get("charset", ""))
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(int(tag[1]))
        elif tag == "a":
            self._a = {"href": a.get("href"), "label": a.get("aria-label", ""), "text": "", "rel": a.get("rel", ""), "target": a.get("target", "")}
        elif tag == "form":
            self.forms.append(a)
        elif tag in ("input", "select", "textarea") and a.get("type") != "hidden":
            self.controls.append((tag, a, self._label_depth > 0))
        elif tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self.labels_for.add(a["for"])
        elif tag == "svg":
            self.svgs.append(a)
        elif tag == "script":
            self.scripts.append(a)
        if tag in ("title", "style", "script"):
            self._in, self._text = tag, []
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        a = self._attrs(tag, attrs)
        self.tags.append((tag, a))
        if tag == "meta":
            key = a.get("name") or a.get("property") or ("charset" if "charset" in a else "")
            if key:
                self.meta[key.lower()] = a.get("content", a.get("charset", ""))
        if tag in ("input", "select", "textarea") and a.get("type") != "hidden":
            self.controls.append((tag, a, self._label_depth > 0))
        if tag == "svg":
            self.svgs.append(a)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if tag == "label":
            self._label_depth = max(0, self._label_depth - 1)
        if tag == "a" and self._a is not None:
            self.links.append(self._a)
            self._a = None
        if self._in == tag:
            text = "".join(self._text)
            if tag == "title":
                self.title = text.strip()
            elif tag == "style":
                self.styles.append(text)
            elif tag == "script":
                self.scripts[-1]["_text"] = text
            self._in = None
        if not self.stack:
            self.errors.append(f"</{tag}> with nothing open")
            return
        if self.stack[-1] == tag:
            self.stack.pop()
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append(f"<{self.stack.pop()}> not closed before </{tag}>")
            self.stack.pop()
        else:
            self.errors.append(f"</{tag}> closes nothing")

    def handle_data(self, data):
        if self._in:
            self._text.append(data)
        if self._a is not None:
            self._a["text"] += data


def _tap_rules(css: str) -> bool:
    need = (r"\.btn\{[^}]*min-height:(4[4-9]|[5-9]\d)px", r"\.nav a\{[^}]*min-height:4[4-9]px", r"input,textarea,select\{[^}]*min-height:(4[4-9]|[5-9]\d)px",
            r"\.menu summary\{[^}]*height:4[4-9]px")
    return all(re.search(p, css) for p in need)


def check_page(text: str, name: str, palette=None, pairs=(), mode="demo") -> dict:
    p = Page()
    p.feed(text)
    p.close()
    css = "\n".join(s for s in p.styles if isinstance(s, str))
    res = []                                            # (category, weight, ok, message, hard)

    def add(cat, w, ok, msg, hard=False):
        res.append({"cat": cat, "w": w, "ok": bool(ok), "msg": msg, "hard": bool(hard) and not ok})

    errors = p.errors + [f"<{t}> never closed" for t in p.stack]
    add("best_practices", 10, not errors, "valid HTML: every tag closed in order" if not errors else "HTML errors: " + "; ".join(errors[:4]), hard=True)
    add("best_practices", 3, p.doctype, "<!doctype html> first")
    add("accessibility", 4, not p.dupe_ids, "ids are unique" if not p.dupe_ids else "duplicate ids: " + ", ".join(p.dupe_ids[:4]), hard=True)
    hot = [f"{t} {k}={u}" for t, k, u in p.resources if external(u)]
    css_urls = [u for u in re.findall(r"url\(\s*['\"]?([^'\")]+)", css) if external(u)] + ([m for m in re.findall(r"@import[^;]+", css)] if "@import" in css else [])
    add("performance", 10, not hot and not css_urls, "nothing loaded from another site (no hotlinked photo, font, script or stylesheet)" if not (hot or css_urls)
        else "loads from another site: " + "; ".join((hot + css_urls)[:4]), hard=True)
    add("performance", 4, not re.search(r"@font-face|fonts\.googleapis|use\.typekit", css + text), "no web fonts (system fonts show instantly)")
    vp = p.meta.get("viewport", "")
    add("seo", 6, "width=device-width" in vp, "phone viewport (width=device-width)" if "width=device-width" in vp else "no phone viewport meta", hard=True)
    add("best_practices", 2, p.meta.get("charset", "").lower() == "utf-8", "utf-8 declared")
    add("accessibility", 4, bool(p.html_lang), f'<html lang="{p.html_lang}">' if p.html_lang else "no lang on <html>")
    add("accessibility", 6, p.headings.count(1) == 1, f"one h1 ({p.headings.count(1)} found)", hard=True)
    order_ok = all(b - a <= 1 for a, b in zip(p.headings, p.headings[1:]))
    add("accessibility", 3, order_ok, "headings in order (no level skipped)" if order_ok else f"a heading level is skipped: {p.headings}")
    ctrl_bad = [a.get("name") or tag for tag, a, wrapped in p.controls if not wrapped and a.get("id") not in p.labels_for and not a.get("aria-label")]
    add("accessibility", 8, not ctrl_bad, "every form field has a label" if not ctrl_bad else "fields without a label: " + ", ".join(ctrl_bad), hard=True)
    svg_bad = [i for i, a in enumerate(p.svgs) if not (a.get("aria-hidden") == "true" or (a.get("role") == "img" and a.get("aria-label")))]
    add("accessibility", 4, not svg_bad, "every picture is named or hidden from screen readers" if not svg_bad else f"{len(svg_bad)} svg without a name or aria-hidden")
    imgs = [a for t, a in p.tags if t == "img" and "alt" not in a]
    add("accessibility", 3, not imgs, "every <img> has alt text" if not imgs else f"{len(imgs)} images without alt")
    empty_links = [l.get("href") for l in p.links if not (l["text"].strip() or l["label"])]
    add("accessibility", 4, not empty_links, "every link has words" if not empty_links else "links without words: " + ", ".join(str(x) for x in empty_links[:3]))
    add("accessibility", 3, bool(re.search(r':focus-visible\{[^}]*outline', css)) and 'class="skip"' in text, "focus ring and a skip link")
    add("accessibility", 3, "prefers-reduced-motion" in css, "reduced motion respected")
    add("accessibility", 5, _tap_rules(css), "tap targets at least 44 px (buttons, links, fields, menu)")
    if palette:
        low = [f"{a}/{b} {contrast(palette[a], palette[b])}:1 (needs {m})" for a, b, m in pairs if a in palette and b in palette and contrast(palette[a], palette[b]) < m]
        add("accessibility", 10, not low, f"colour contrast: all {len(pairs)} text pairs pass WCAG AA" if not low else "low contrast: " + "; ".join(low), hard=True)
    add("best_practices", 4, not p.inline_handlers and "javascript:" not in text.lower(), "no inline onclick= / javascript: links (works with the strict security header)")
    ext = [l for l in p.links if l.get("href") and l["href"].startswith("http")]
    add("best_practices", 3, all(l["href"].startswith("https://") for l in ext), "outside links use https")
    add("best_practices", 2, all("noopener" in l["rel"] for l in ext if l["target"] == "_blank"), "new-tab links have rel=noopener")
    scripts = [s for s in p.scripts if s.get("src")]
    add("performance", 4, all("defer" in s or "async" in s for s in scripts), "scripts are deferred (the page shows before they run)")
    tlen, dlen = len(p.title), len(p.meta.get("description", ""))
    add("seo", 5, 10 <= tlen <= 70, f"title {tlen} characters (10-70)")
    add("seo", 4, 50 <= dlen <= 160 or name != "index.html", f"description {dlen} characters (50-160)")
    ld = [s.get("_text", "") for s in p.scripts if s.get("type") == "application/ld+json"]
    ld_ok = False
    for t in ld:
        try:
            d = json.loads(t)
            ld_ok = bool(d.get("@type") and d.get("name"))
        except ValueError:
            ld_ok = False
    add("seo", 4, ld_ok or name != "index.html", "structured data (schema.org LocalBusiness) parses")
    robots = p.meta.get("robots", "")
    add("seo", 3, ("noindex" in robots) if mode == "demo" else ("noindex" not in robots), "a preview is kept out of Google (noindex)" if mode == "demo" else "the live site can be found on Google")
    tel = [l["href"] for l in p.links if (l.get("href") or "").startswith("tel:")]
    add("seo", 3, all(re.fullmatch(r"tel:\+\d{8,15}", t) for t in tel), "phone links are in +1XXXXXXXXXX form" + ("" if tel else " (no phone on file)"))
    return {"page": name, "bytes": len(text.encode("utf-8")), "checks": res}


def check_dir(folder: str, palette=None, pairs=(), mode="demo") -> dict:
    pages, total, sizes = [], 0, {}
    for n in sorted(os.listdir(folder)):
        fp = os.path.join(folder, n)
        if not os.path.isfile(fp):
            continue
        sizes[n] = os.path.getsize(fp)
        total += sizes[n]
        if n.endswith(".html"):
            with open(fp, encoding="utf-8") as fh:
                pages.append(check_page(fh.read(), n, palette if n == "index.html" else None, pairs, mode))
    extra = []

    def add(cat, w, ok, msg, hard=False):
        extra.append({"cat": cat, "w": w, "ok": bool(ok), "msg": msg, "hard": bool(hard) and not ok})

    idx = sizes.get("index.html", 0)
    add("performance", 8, idx <= BUDGET_PAGE, f"home page {idx / 1024:.1f} KB (budget {BUDGET_PAGE // 1000} KB)", hard=idx > HARD_PAGE)
    add("performance", 4, total <= BUDGET_TOTAL, f"whole site {total / 1024:.1f} KB (budget {BUDGET_TOTAL // 1000} KB)")
    add("performance", 3, len([n for n in sizes if n.endswith((".js", ".css", ".svg", ".png", ".jpg", ".webp"))]) <= 4, "few files to load (the CSS is inline)")
    hdr = ""
    if os.path.isfile(os.path.join(folder, "_headers")):
        with open(os.path.join(folder, "_headers"), encoding="utf-8") as fh:
            hdr = fh.read()
    add("best_practices", 4, "Content-Security-Policy" in hdr and "X-Content-Type-Options" in hdr, "security headers file (_headers) for Netlify / Cloudflare")
    add("best_practices", 2, all(os.path.isfile(os.path.join(folder, n)) for n in ("404.html", "thanks.html", "favicon.svg", "robots.txt")), "404, thank-you page, icon and robots.txt present")
    allc = [c for pg in pages for c in pg["checks"]] + extra
    scores = {}
    for cat in ("performance", "accessibility", "best_practices", "seo"):
        cs = [c for c in allc if c["cat"] == cat]
        tw = sum(c["w"] for c in cs) or 1
        scores[cat] = round(100 * sum(c["w"] for c in cs if c["ok"]) / tw)
    hard = sorted({(pg["page"] + ": " if c in pg["checks"] else "") + c["msg"] for pg in pages for c in pg["checks"] if c["hard"]} | {c["msg"] for c in extra if c["hard"]})
    fixes = sorted({c["msg"] for c in allc if not c["ok"]})
    return {"ok": not hard, "scores": scores, "hard_fails": hard, "to_fix": fixes, "bytes_total": total, "sizes": sizes,
            "pages": [{"page": pg["page"], "bytes": pg["bytes"], "failed": [c["msg"] for c in pg["checks"] if not c["ok"]]} for pg in pages],
            "passed": sorted({c["msg"] for c in allc if c["ok"]}), "mode": mode}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    folder = argv[0]
    palette, pairs = None, ()
    sj = os.path.join(os.path.dirname(os.path.abspath(folder)), "site.json")
    if os.path.isfile(sj):
        from .build_site import CONTRAST, THEMES
        with open(sj, encoding="utf-8") as fh:
            palette, pairs = THEMES[json.load(fh)["theme"]]["palette"], CONTRAST
    mode = "demo"
    try:
        with open(os.path.join(folder, "robots.txt"), encoding="utf-8") as fh:
            mode = "demo" if "Disallow: /" in fh.read() else "final"
    except OSError:
        pass
    r = check_dir(folder, palette, pairs, mode)
    s = r["scores"]
    print(f"Performance {s['performance']}  Accessibility {s['accessibility']}  Best practices {s['best_practices']}  SEO {s['seo']}   "
          f"({r['bytes_total'] / 1024:.1f} KB, {'OK' if r['ok'] else 'NOT READY'})")
    for f in r["hard_fails"]:
        print("  MUST FIX:", f)
    for f in r["to_fix"]:
        if f not in r["hard_fails"]:
            print("  could be better:", f)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
