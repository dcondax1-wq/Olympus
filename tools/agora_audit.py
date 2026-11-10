#!/usr/bin/env python3
"""AGORA theme audit (docs/DESIGN_AGORA.md BANNED list). stdlib; playwright optional.

  python tools/agora_audit.py                 static scan, table per app
  python tools/agora_audit.py --app kalshi    one app
  python tools/agora_audit.py --render        also load /<id>/?demo=1&q=low at 390x844 (one browser, 25 s per app)
  python tools/agora_audit.py --json out.json machine readable result
Exit 1 on any hard FAIL (CSS/HTML neon, banned font, wrong theme-color, glow shadow, pure #000 bg / #fff text,
rendered page > 30% cool blue/cyan/violet). JS-only hits are WARN (scene palettes) unless --strict-js.
"""
import argparse, colorsys, json, os, re, sys, threading, http.server, socketserver, functools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOTS = [os.path.join(ROOT, "tools", "web_public"), os.path.join(ROOT, "web_next")]
SKIP_DIRS = {"icon_options", "brand", "node_modules", "vendor", "fonts", "jarvis_legacy"}
SKIP_FILE = re.compile(r"(\.min\.|three(\.module)?\.js$|OFL\.txt|/lib/|/vendor/)")
EXTS = (".css", ".js", ".mjs", ".html")
THEME = "#14110e"

HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
# old purple/blue accents found by grep (named explicitly so they always show up, whatever the HSL says)
OLD_ACCENTS = {"#a68bff", "#b79bff", "#7fd0ff", "#b388ff", "#a78bfa", "#8b5cf6", "#7c3aed", "#a855f7", "#c084fc",
               "#22d3ee", "#2ee59d", "#ff2bd6", "#3ee0c8", "#6d28d9", "#4f9bff", "#38bdf8", "#67e8f9", "#7c4dff"}
FONT = re.compile(r"orbitron|rajdhani|share tech|vt323|press start|audiowide|exo 2|major mono|space mono|\bmono-display", re.I)
WORDS = re.compile(r"\b(cyber\w*|neural|quantum|holographic|hologram|matrix|terminal|scanner|uplink)\b", re.I)
SHADOW = re.compile(r"text-shadow\s*:\s*([^;}]+)", re.I)
LSPACE = re.compile(r"letter-spacing\s*:\s*([\d.]+)(em|px)", re.I)
RADIAL = re.compile(r"radial-gradient\([^;]*", re.I)
BG000 = re.compile(r"(background(?:-color)?\s*:\s*[^;}]*?)(#000000|#000\b|\bblack\b)", re.I)
TXTFFF = re.compile(r"(?<![-\w])color\s*:\s*(#ffffff|#fff\b|\bwhite\b)", re.I)
THEME_META = re.compile(r'<meta[^>]+name=["\']theme-color["\'][^>]*content=["\']([^"\']+)["\']', re.I)


def hsl(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    H, L, S = colorsys.rgb_to_hls(r, g, b)
    return H * 360, S, L


def is_neon(h):
    """Cool or magenta, saturated, bright enough to glow: cyan/mint 150-200, blue/violet 205-330 (aegean #4b7a99 passes)."""
    if h.lower() in OLD_ACCENTS:
        return True
    H, S, L = hsl(h)
    return S >= 0.5 and 0.38 <= L <= 0.92 and 150 <= H <= 335 and not (L > 0.9)


def neon_rgba(line):
    out = []
    for m in re.finditer(r"rgba?\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)", line):
        r, g, b = (int(x) / 255 for x in m.groups())
        H, L, S = colorsys.rgb_to_hls(r, g, b)
        if S >= .5 and .38 <= L <= .92 and 150 <= H * 360 <= 335:
            out.append(m.group(0))
    return out


def apps():
    found = {}
    for base in ROOTS:
        if not os.path.isdir(base):
            continue
        tag = "web_next" if base.endswith("web_next") else ""
        if tag:
            found["web_next"] = base
            continue
        for d in sorted(os.listdir(base)):
            p = os.path.join(base, d)
            if os.path.isdir(p) and d not in SKIP_DIRS:
                found[d] = p
        found["(root pages)"] = base  # loose *.css/js/html in web_public itself
    return found


def files_of(name, path):
    out = []
    if name == "(root pages)":
        for f in sorted(os.listdir(path)):
            fp = os.path.join(path, f)
            if os.path.isfile(fp) and f.endswith(EXTS) and not SKIP_FILE.search(fp):
                out.append(fp)
        return out
    for dp, dn, fn in os.walk(path):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            fp = os.path.join(dp, f)
            if f.endswith(EXTS) and not SKIP_FILE.search(fp.replace(os.sep, "/")):
                out.append(fp)
    return sorted(out)


def scan_file(fp):
    """returns dict kind -> list[(lineno, text)] and whether file is CSS/HTML (hard) or JS (soft)."""
    hits = {}
    try:
        text = open(fp, encoding="utf-8", errors="replace").read()
    except OSError:
        return hits
    if len(text) > 2_500_000:
        return hits
    lines = text.split("\n")
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if len(s) > 400:  # minified: keep a window around hit later
            pass

        def add(k, v=None):
            hits.setdefault(k, []).append((i, (v or s)[:140]))
        for m in HEX.finditer(ln):
            if is_neon(m.group(0)):
                add("neon", ln[max(0, m.start() - 40):m.end() + 20].strip())
                break
        else:
            if neon_rgba(ln):
                add("neon", s)
        for m in SHADOW.finditer(ln):
            v = m.group(1).strip().lower()
            if v not in ("none", "0 0 0 transparent", "inherit", "unset") and (re.search(r"\b0(px)?\s+0(px)?\s+\d+", v) or neon_rgba(v) or any(is_neon(h.group(0)) for h in HEX.finditer(v))):
                add("glow", m.group(0))
        if FONT.search(ln):
            add("font", s)
        for m in LSPACE.finditer(ln):
            val = float(m.group(1))
            if (m.group(2) == "em" and val > .06) or (m.group(2) == "px" and val > 1.2):
                add("spacing", m.group(0)); break
        if WORDS.search(ln) and not ln.lstrip().startswith(("//", "/*", "*")) and re.search(r"[\"'>]\s*[^\"'<]*\b(cyber|neural|quantum|holographic|matrix|terminal|scanner|uplink)", ln, re.I):
            add("words", s)
        if BG000.search(ln):
            add("black", s)
        if TXTFFF.search(ln):
            add("white", s)
        if RADIAL.search(ln) and (any(is_neon(h.group(0)) for h in HEX.finditer(ln)) or neon_rgba(ln)):
            add("radial", s)
    if fp.endswith(".html"):
        m = THEME_META.search(text)
        if m and m.group(1).strip().lower() != THEME:
            hits.setdefault("theme", []).append((text[:m.start()].count("\n") + 1, m.group(0)[:100]))
        if "<html" in text.lower() and 'data-theme="agora"' not in text and "/olympus/" in text.replace("\\", "/") and "../" in text:
            pass
    return hits


HARD_CSS = ("neon", "glow", "font", "theme", "black", "white")
KINDS = ["neon", "glow", "font", "spacing", "words", "black", "white", "radial", "theme"]


def static_scan(only=None):
    res = {}
    for name, path in apps().items():
        if only and name not in only:
            continue
        agg = {k: [] for k in KINDS}
        hard = {k: 0 for k in KINDS}
        for fp in files_of(name, path):
            rel = os.path.relpath(fp, ROOT)
            h = scan_file(fp)
            code = fp.endswith(".js") or fp.endswith(".mjs")
            if "theme" in h and not code:
                pass
            for k, v in h.items():
                for ln, t in v:
                    agg[k].append((rel, ln, t, code))
                    if not code and k in HARD_CSS:
                        hard[k] += 1
                    if code and k in ("font", "black") and k != "x":
                        pass
        res[name] = {"counts": {k: len(v) for k, v in agg.items()}, "hard": hard, "hits": agg}
    return res


def static_fail(r):
    return sum(r["hard"].values())


# ---------- rendered scan ----------
def serve(port):
    root = ROOTS[0]

    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Q, directory=root)
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", port), h)
    srv.allow_reuse_address = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def pixel_stats(png_path):
    """cool% (hue 170-330, S>.35, L .2-.9), mean bg colour of top strip; needs Pillow, else returns None."""
    try:
        from PIL import Image
    except Exception:
        return None
    im = Image.open(png_path).convert("RGB")
    im = im.resize((98, 211))
    px = list(im.getdata())
    cool = 0
    for r, g, b in px:
        H, L, S = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if S > .35 and .2 < L < .92 and 170 <= H * 360 <= 330:
            cool += 1
    n = len(px)
    bg = im.getpixel((5, 5))
    # dominant (quantised) colours
    q = {}
    for r, g, b in px:
        k = (r // 32 * 32, g // 32 * 32, b // 32 * 32)
        q[k] = q.get(k, 0) + 1
    dom = sorted(q.items(), key=lambda kv: -kv[1])[:3]
    return {"cool_pct": round(100 * cool / n, 1), "bg": "#%02x%02x%02x" % bg, "dominant": ["#%02x%02x%02x %d%%" % (k + (round(100 * v / n),)) for k, v in dom]}


def render_scan(ids, shotdir, port=8799, per=25):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("playwright missing: rendered scan skipped"); return {}
    os.makedirs(shotdir, exist_ok=True)
    srv = serve(port)
    out = {}
    with sync_playwright() as p:
        for aid in ids:
            if not os.path.isfile(os.path.join(ROOTS[0], aid, "index.html")):
                continue
            b = p.chromium.launch(args=["--disable-gpu", "--use-gl=swiftshader", "--no-sandbox"])
            try:
                ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, service_workers="block")
                pg = ctx.new_page()
                pg.set_default_timeout(per * 1000)
                errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)[:80]))
                pg.goto(f"http://127.0.0.1:{port}/{aid}/?demo=1&q=low", wait_until="domcontentloaded", timeout=per * 1000)
                pg.wait_for_timeout(2500)
                shot = os.path.join(shotdir, aid + ".png")
                # skip canvases' cost: screenshot is cheap; do not wait for animations
                pg.screenshot(path=shot, animations="disabled", timeout=per * 1000)
                st = pixel_stats(shot) or {}
                try:
                    st["body_bg"] = pg.evaluate("getComputedStyle(document.body).backgroundColor")
                    st["theme_attr"] = pg.evaluate("document.documentElement.dataset.theme||''")
                except Exception:
                    pass
                st["errors"] = len(errs)
                st["shot"] = os.path.relpath(shot, ROOT) if shot.startswith(ROOT) else shot
                out[aid] = st
            except Exception as e:
                out[aid] = {"error": str(e)[:100]}
            finally:
                try: b.close()
                except Exception: pass
    srv.shutdown()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", action="append")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--shots", default=os.path.join(ROOT, "research", "agora_shots"))
    ap.add_argument("--json")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--strict-js", action="store_true", help="JS hits also count as hard FAIL")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    res = static_scan(a.app)
    fails = 0
    rows = sorted(res.items(), key=lambda kv: -(sum(kv[1]["counts"].values())))
    print("%-16s %5s %5s %5s %5s %5s %5s %5s %5s %5s  %s" % ("app", *KINDS, "HARD"))
    for name, r in rows:
        c = r["counts"]
        hard = static_fail(r)
        if a.strict_js:
            hard = sum(c[k] for k in HARD_CSS)
        fails += hard
        if sum(c.values()) == 0:
            continue
        print("%-16s " % name + " ".join("%5d" % c[k] for k in KINDS) + "  %s" % ("FAIL %d" % hard if hard else "warn"))
    clean = [n for n, r in res.items() if sum(r["counts"].values()) == 0]
    print("clean apps: %d / %d" % (len(clean), len(res)))
    if not a.quiet:
        for name, r in rows:
            if sum(r["counts"].values()) == 0:
                continue
            print("\n== %s" % name)
            shown = 0
            for k in KINDS:
                for rel, ln, t, code in r["hits"][k][:a.top]:
                    print("  [%s%s] %s:%d  %s" % (k, "/js" if code else "", rel, ln, t))
                    shown += 1
    rend = {}
    if a.render:
        ids = a.app or [n for n in res if n not in ("web_next", "(root pages)")]
        rend = render_scan(ids, a.shots)
        print("\nRENDERED (390x844 ?demo=1&q=low)")
        print("%-16s %6s %-9s %-9s %s" % ("app", "cool%", "bg", "attr", "dominant"))
        for aid, s in rend.items():
            if "error" in s:
                print("%-16s ERROR %s" % (aid, s["error"])); continue
            bad = s.get("cool_pct", 0) > 30
            if bad:
                fails += 1
            print("%-16s %6s %-9s %-9s %s%s" % (aid, s.get("cool_pct"), s.get("bg"), s.get("theme_attr"), ", ".join(s.get("dominant", [])), "  FAIL cool>30%" if bad else ""))
    if a.json:
        json.dump({"static": {n: {"counts": r["counts"], "hard": r["hard"]} for n, r in res.items()}, "rendered": rend}, open(a.json, "w"), indent=1)
    print("\nHARD FAILS: %d" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
