"""Rebuild the glyph outline files the brand kit uses (only needed if you want other fonts; the JSON files are committed).

    python -m money_machines.fonts.build_glyphs            # needs fontTools (pip install fonttools) and the two open fonts below

Why: a logo must look the same on every computer, so the brand kit draws the letters as vector paths (no font has to be
installed on the PC that opens the SVG). The outlines come from two fonts under the SIL Open Font License 1.1 (OFL), which
allows this (FONTS_LICENSE.txt): Inter (sans, by The Inter Project Authors) and Caladea (serif, by The Caladea Project Authors).
The JSON files are a derived copy of those fonts and stay under the OFL; logos made with them are documents and are not
restricted (OFL: "does not apply to any document created using the fonts").

Inter Medium ("text") is for taglines. Output per font: {"name", "license", "upm", "ascender", "descender", "cap", "x", "glyphs": {char: [advance, "svg path"]},
"kern": {"AV": -120, ...}} in font units, y pointing DOWN (SVG), baseline at y = 0.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = {
    "sans": ("/usr/share/fonts/opentype/inter/Inter-Bold.otf", "Inter Bold (c) 2016 The Inter Project Authors, OFL-1.1"),
    "serif": ("/usr/share/fonts/truetype/crosextra/Caladea-Bold.ttf", "Caladea Bold (c) 2012 The Caladea Project Authors, OFL-1.1"),
    "text": ("/usr/share/fonts/opentype/inter/Inter-Medium.otf", "Inter Medium (c) 2016 The Inter Project Authors, OFL-1.1"),
}
CHARS = [chr(c) for c in range(32, 127)] + [chr(c) for c in range(0xC0, 0x100) if c not in (0xD7, 0xF7)] + list("’‘“”–—•·")
KERN_CHARS = [chr(c) for c in range(32, 127)]


def _pair_values(font, gmap):
    """{(left glyph, right glyph): x advance adjustment} from the GPOS 'kern' feature (formats 1 and 2, extension lookups)."""
    out = {}
    if "GPOS" not in font:
        return out
    gpos = font["GPOS"].table
    idx = set()
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "kern":
            idx.update(fr.Feature.LookupListIndex)
    wanted = set(gmap.values())
    for li in sorted(idx):
        lk = gpos.LookupList.Lookup[li]
        subs = []
        for st in lk.SubTable:
            if lk.LookupType == 9:
                subs.append(st.ExtSubTable)
            elif lk.LookupType == 2:
                subs.append(st)
        for st in subs:
            if getattr(st, "LookupType", 2) != 2 and not hasattr(st, "Format"):
                continue
            cov = st.Coverage.glyphs
            if st.Format == 1:
                for gi, first in enumerate(cov):
                    if first not in wanted:
                        continue
                    for pvr in st.PairSet[gi].PairValueRecord:
                        if pvr.SecondGlyph in wanted and (first, pvr.SecondGlyph) not in out:
                            v = getattr(pvr.Value1, "XAdvance", 0) if pvr.Value1 else 0
                            out[(first, pvr.SecondGlyph)] = v or 0
            elif st.Format == 2:
                c1 = st.ClassDef1.classDefs if st.ClassDef1 else {}
                c2 = st.ClassDef2.classDefs if st.ClassDef2 else {}
                for first in cov:
                    if first not in wanted:
                        continue
                    rec = st.Class1Record[c1.get(first, 0)]
                    for second in wanted:
                        if (first, second) in out:
                            continue
                        r2 = rec.Class2Record[c2.get(second, 0)]
                        v = getattr(r2.Value1, "XAdvance", 0) if r2.Value1 else 0
                        out[(first, second)] = v or 0
    return out


def build(kind: str) -> dict:
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont

    path, credit = FONTS[kind]
    f = TTFont(path)
    gs = f.getGlyphSet()
    cmap = f.getBestCmap()
    os2 = f["OS/2"]
    glyphs, gmap = {}, {}
    for ch in CHARS:
        g = cmap.get(ord(ch))
        if not g:
            continue
        pen = SVGPathPen(gs, ntos=lambda v: str(int(round(v))))
        gs[g].draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
        glyphs[ch] = [int(f["hmtx"][g][0]), pen.getCommands()]
        if ch in KERN_CHARS:
            gmap[ch] = g
    rev = {v: k for k, v in gmap.items()}
    kern = {rev[a] + rev[b]: int(v) for (a, b), v in _pair_values(f, gmap).items() if v}
    return {"name": credit.split(" (c)")[0], "license": credit, "upm": int(f["head"].unitsPerEm),
            "ascender": int(f["hhea"].ascent), "descender": int(f["hhea"].descent),
            "cap": int(getattr(os2, "sCapHeight", 0) or 0), "x": int(getattr(os2, "sxHeight", 0) or 0),
            "glyphs": glyphs, "kern": dict(sorted(kern.items()))}


def main() -> int:
    for kind in FONTS:
        if not os.path.exists(FONTS[kind][0]):
            print(f"missing font file {FONTS[kind][0]} (install fonts-inter / fonts-crosextra-caladea)")
            return 1
        data = build(kind)
        out = os.path.join(HERE, f"glyphs_{kind}.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        print(f"{out}: {len(data['glyphs'])} glyphs, {len(data['kern'])} kerning pairs, {os.path.getsize(out) // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
