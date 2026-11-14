"""OLYMPUS theme reach: rewrite a stylesheet's AGORA colour literals as theme slots (docs/OLYMPUS_DESIGN.md "Themes", olympus/themes.js).

    python tools/theme_tokenize.py <file.css | file.html> ...            dry run: what would change, per file
    python tools/theme_tokenize.py --apply <files> ...                    rewrite in place (idempotent: run it again after a merge)
    python tools/theme_tokenize.py --apply --families n <files>           only the neutrals (an app that keeps its own accent, e.g. Kalshi)

Every colour literal in a declaration value becomes var(--oly-th-<slot>, <the literal>) (hex) or rgba(var(--oly-th-<slot>-rgb, r,g,b as written), a)
(rgb / rgba), AGORA's heading serif stack ('Iowan Old Style', ... serif) becomes var(--oly-th-display, <the stack>), and a custom property that is a bare 'r, g, b' triplet becomes var(--oly-th-<slot>-rgb, r, g, b). No stylesheet defines --oly-th-*: only olympus/themes.js paints them, and only for a theme that is not the default, so on
the default (AGORA) every value computes exactly as before (the literal is the fallback). The slot = the family + the HSL lightness on
themes.js's GRID: n = warm neutrals (chroma <= 40: pages, panels, lines, text), a = golds / bronzes (hue 20-62), g = greens (62-170, the
gains), r = reds / terracottas (< 20 or >= 335, the losses), warn = AGORA's sun, info / infot = AGORA's aegean blue #4b7a99 / #7fa7c2
(2026-11-14). Pure black / white, other blues and violets (an app's own
identity colours) and 4 / 8 digit hex are left as they are. Never touched: selectors, comments, strings, url(...), a value already
inside var(--oly-th-...), and every rule scoped to a light look of its own ([data-theme="light"], [data-oly-scheme="light"],
prefers-color-scheme: light; a :not(...) of them is the dark look and is read). In an .html file only the <style> blocks are read; in a
.js file only the values of colour properties inside its CSS strings (see tokenize_js).
"""
from __future__ import annotations

import argparse
import colorsys
import os
import re
import sys

GRID = {"n": (0, 100, 2.5), "a": (15, 90, 5), "g": (15, 90, 5), "r": (15, 90, 5)}      # = olympus/themes.js GRID (the test checks it)
WARN = {(224, 176, 96), (220, 174, 106)}                                               # AGORA's sun (--ag-sun, Zenith's --warn)
# AGORA's aegean blue (2026-11-14, team T2): the information colour, a fill and a text ink; every look paints them readable on its own page
INFO = {(75, 122, 153): "info", (127, 167, 194): "infot"}
# the bots' identity colours (2026-11-14, team T2): a look never repaints them (Zlarior's blue and BLITZ's violet are not warm, ATLAS's orange is)
KEEP = {(255, 154, 61), (255, 106, 26)}
LIGHT = re.compile(r"data-theme\s*=\s*[\"']?light|data-oly-scheme\s*=\s*[\"']?light|prefers-color-scheme\s*:\s*light", re.I)
NOT = re.compile(r":not\((?:[^()]|\([^()]*\))*\)")


def is_light(prelude):
    """a rule scoped to a light look of its own (:not([data-theme="light"]) is the dark look: tokenized)"""
    p = prelude
    while True:
        q = NOT.sub("", p)
        if q == p:
            break
        p = q
    return bool(LIGHT.search(p))


RULE_BLOCKS = re.compile(r"^\s*@(media|supports|layer|container|document|keyframes|-webkit-keyframes)\b", re.I)
HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F\w-])")
SERIF = re.compile(r"([\"']Iowan Old Style[\"']\s*,[^;{}()]*?(?<![\w-])(?:sans-serif|serif))(?![\w-])")      # AGORA's heading serif: a theme's heading font
TRIPLET = re.compile(r"^(\s*)((\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3}))(\s*)$")
# rgb() / rgba(): the three numbers are kept exactly as written (the fallback), so a custom property holding one computes to the same text
RGB = re.compile(r"(rgba?\(\s*)((\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3}))(\s*(?:,\s*[\d.]+%?\s*)?\))", re.I)


def lightness(r, g, b):
    return (max(r, g, b) + min(r, g, b)) / 5.1


def slot(r, g, b, families="nagrwi"):
    """the theme slot of one colour, or None (left as it is)"""
    if (r, g, b) in ((0, 0, 0), (255, 255, 255)) or (r, g, b) in KEEP:
        return None
    if (r, g, b) in WARN:
        return "warn" if "w" in families else None
    if (r, g, b) in INFO:
        return INFO[(r, g, b)] if "i" in families else None
    c = max(r, g, b) - min(r, g, b)
    if c <= 40:
        f = "n"
    else:
        h = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0] * 360
        f = "a" if 20 <= h < 62 else "g" if 62 <= h < 170 else "r" if (h < 20 or h >= 335) else None
    if not f or f not in families:
        return None
    g0, g1, st = GRID[f]
    n = round((g1 - g0) / st)
    i = max(0, min(n, round((lightness(r, g, b) - g0) / st)))
    return f"{f}{i}"


def _value(v, families, counts):
    """rewrite the colours of one declaration value (url(), strings and var(--oly-th-...) kept whole)"""
    if "--oly-th-display" not in v:                             # AGORA's heading serif stack (quoted names: before the strings are kept whole)
        v, k = SERIF.subn(lambda m: f"var(--oly-th-display, {m.group(1)})", v)
        counts[0] += k
    out, i = [], 0
    protect = re.compile(r"url\(|var\(--oly-th-|\"|'")
    while i < len(v):
        m = protect.search(v, i)
        j = m.start() if m else len(v)
        out.append(_colours(v[i:j], families, counts))
        if not m:
            break
        k = m.start()
        if m.group(0) in ('"', "'"):
            e = v.find(m.group(0), k + 1)
            e = len(v) if e < 0 else e + 1
        else:                                                   # url( ... ) / var(--oly-th- ... ) with nested parens
            depth, e = 0, k
            while e < len(v):
                if v[e] == "(":
                    depth += 1
                elif v[e] == ")":
                    depth -= 1
                    if depth == 0:
                        e += 1
                        break
                e += 1
        out.append(v[k:e])
        i = e
    return "".join(out)


def _colours(s, families, counts):
    def hx(m):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[x:x + 2], 16) for x in (0, 2, 4))
        sl = slot(r, g, b, families)
        if not sl:
            return m.group(0)
        counts[0] += 1
        return f"var(--oly-th-{sl}, {m.group(0)})"

    def rg(m):
        r, g, b = int(m.group(3)), int(m.group(4)), int(m.group(5))
        sl = slot(r, g, b, families) if max(r, g, b) <= 255 else None
        if not sl:
            return m.group(0)
        counts[0] += 1
        return f"{m.group(1)}var(--oly-th-{sl}-rgb, {m.group(2)}){m.group(6)}"
    return RGB.sub(rg, HEX.sub(hx, s))


def tokenize_css(css, families="nagrwi"):
    """(new css, number of literals rewritten)"""
    out, i, n = [], 0, len(css)
    stack = []                    # one entry per open block: (kind 'rules' | 'decl', skip)
    buf_start = 0                 # where the current prelude / declaration started
    counts = [0]
    while i < n:
        ch = css[i]
        if css.startswith("/*", i):
            e = css.find("*/", i + 2)
            e = n if e < 0 else e + 2
            i = e
            continue
        if ch in "\"'":
            e = css.find(ch, i + 1)
            i = n if e < 0 else e + 1
            continue
        if ch == "{":
            prelude = css[buf_start:i]
            skip = bool(stack and stack[-1][1]) or is_light(prelude)
            kind = "rules" if RULE_BLOCKS.match(prelude) else "decl"
            stack.append((kind, skip))
            i += 1
            buf_start = i
            continue
        if ch == "}":
            if stack:
                stack.pop()
            i += 1
            buf_start = i
            continue
        if ch == ";" and (not stack or stack[-1][0] == "rules"):
            i += 1
            buf_start = i
            continue
        if ch == ":" and stack and stack[-1][0] == "decl":
            # a declaration value: up to the next ';' or '}' at this level (strings / parens respected)
            j, depth = i + 1, 0
            while j < n:
                c = css[j]
                if css.startswith("/*", j):
                    e = css.find("*/", j + 2)
                    j = n if e < 0 else e + 2
                    continue
                if c in "\"'":
                    e = css.find(c, j + 1)
                    j = n if e < 0 else e + 1
                    continue
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                elif c in ";}" and depth <= 0:
                    break
                j += 1
            if not stack[-1][1]:
                name, val = re.sub(r"/\*.*?\*/", "", css[buf_start:i], flags=re.S).strip(), css[i + 1:j]
                tri = TRIPLET.match(val) if name.startswith("--") else None
                if tri:                                          # '--x-rgb: 200, 162, 74' (read as rgba(var(--x-rgb), a))
                    sl = slot(*(int(tri.group(k)) for k in (3, 4, 5)), families)
                    if sl:
                        counts[0] += 1
                        val = f"{tri.group(1)}var(--oly-th-{sl}-rgb, {tri.group(2)}){tri.group(6)}"
                    out.append((i + 1, j, val))
                else:
                    out.append((i + 1, j, _value(val, families, counts)))
            i = j
            buf_start = j + 1 if j < n and css[j] == ";" else j
            if j < n and css[j] == ";":
                i = j + 1
            continue
        i += 1
    # splice the rewritten values back
    res, last = [], 0
    for a, b, v in out:
        res.append(css[last:a])
        res.append(v)
        last = b
    res.append(css[last:])
    return "".join(res), counts[0]


def tokenize_file(path, families="nagrwi"):
    src = open(path, encoding="utf-8").read()
    if path.endswith((".html", ".htm")):
        total = [0]

        def blk(m):
            new, c = tokenize_css(m.group(2), families)
            total[0] += c
            return m.group(1) + new + m.group(3)
        new = re.sub(r"(<style[^>]*>)(.*?)(</style>)", blk, src, flags=re.S | re.I)
        return src, new, total[0]
    if path.endswith((".js", ".mjs")):
        return (src,) + tokenize_js(src, families)
    new, c = tokenize_css(src, families)
    return src, new, c


JS_DECL = re.compile(r"(?<![\w$.])((?:color|background(?:-color|-image)?|border(?:-(?:top|right|bottom|left))?(?:-color)?|box-shadow|outline(?:-color)?|fill|stroke|"
                     r"text-shadow|caret-color|text-decoration-color|font(?:-family)?|--[\w-]+)\s*:\s*)([^;{}'\"`\n]+)")


def tokenize_js(src, families="nagrwi"):
    """(new source, count): the CSS a script writes into a <style> (or cssText): only the values of colour properties inside its strings
    ('.x{background:#1d1914;color:var(--ag-text,#f3ece0)}'); a colour that is a string of its own (a canvas fillStyle, a three.js colour) is
    never touched. Lines that scope a light look of their own are skipped. Review the diff: it is a text rewrite, not a JS parser."""
    counts = [0]
    out = []
    for line in src.splitlines(keepends=True):
        if is_light(line) or "OLYMPUS_THEMES" in line:
            out.append(line)
            continue
        new = JS_DECL.sub(lambda m: m.group(1) + _value(m.group(2), families, counts), line)
        if re.search(r"(?<![\w-])font(?:-family)?\s*:", new) and "--oly-th-display" not in new:     # a CSS font declaration in this string
            new, k = SERIF.subn(lambda m: f"var(--oly-th-display, {m.group(1)})", new)
            counts[0] += k
        out.append(new)
    return "".join(out), counts[0]


UN_HEX = re.compile(r"var\(--oly-th-[\w-]+, (#[0-9a-fA-F]{3,6})\)")
UN_TRI = re.compile(r"var\(--oly-th-[\w-]+-rgb, ([^()]*)\)")
# the feel (fonts, radius) and the T2 slots written by hand (2026-11-14: the focus ring, the shadows): a fallback with up to two levels of parentheses
UN_FEEL = re.compile(r"var\(--oly-th-(?:display|num|body|radius|radius-s|radius-l|ring|shadow|e1|e2|e3), ((?:[^()]|\((?:[^()]|\([^()]*\))*\))*)\)")


def untokenize(text):
    """the text with every theme slot replaced by its fallback: what the file was before (the default theme's look, by construction)"""
    text = UN_TRI.sub(r"\1", text)
    text = UN_HEX.sub(r"\1", text)
    return UN_FEEL.sub(r"\1", text)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--families", default="nagrwi", help="any of n a g r w i (w = warn, i = AGORA's aegean info blue); default all")
    a = ap.parse_args(argv)
    fam = a.families.replace("warn", "w")
    for f in a.files:
        old, new, c = tokenize_file(f, fam)
        left = len(HEX.findall(re.sub(r"var\(--oly-th-[^()]*(\([^()]*\))?[^()]*\)", "", new))) if not f.endswith(".html") else 0
        print(f"{os.path.relpath(f)}: {c} literals -> theme slots" + ("" if new != old or not c else " (already)") + (f", {left} hex left as they are" if left else ""))
        if a.apply and new != old:
            with open(f, "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
