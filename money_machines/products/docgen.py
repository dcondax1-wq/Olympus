"""A tiny document model for the digital products (team D2, 2026-11-14): one list of blocks -> an editable .docx (python-docx) and the
same document as HTML (for the PDF guides and the cover thumbnails).

Blocks (tuples): ("h1", t) ("h2", t) ("h3", t) ("p", t) ("small", t) ("ul", [t]) ("ol", [t]) ("check", [t]) ("table", head, rows)
("note", t) ("warn", t) ("email", subject, body) ("script", [(who, line)]) ("fields", [(label, hint)]) ("sign", [label]) ("lines", n)
("pagebreak",). Inline: **bold**; [words in brackets] are fill-ins (yellow highlight in Word, a soft mark in HTML).
"""
from __future__ import annotations

import html as _html
import re

INK, ACCENT, MUTED, SOFT, LINE, WARN = "1D1A16", "8A5A1C", "5F574B", "F6F2EA", "D8CFBF", "FDF1E7"
TOKEN = re.compile(r"(\*\*.+?\*\*|\[[^\]\n]+\])")


def _runs(text: str):
    for part in TOKEN.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            yield part[2:-2], "b"
        elif part.startswith("[") and part.endswith("]"):
            yield part, "fill"
        else:
            yield part, ""


# ------------------------------------------------------------------------------------------------ HTML
def inline_html(text: str) -> str:
    out = []
    for t, kind in _runs(text):
        e = _html.escape(t)
        out.append(f"<b>{e}</b>" if kind == "b" else f'<mark>{e}</mark>' if kind == "fill" else e)
    return "".join(out).replace("\n", "<br>")


DOC_CSS = """@page{size:Letter;margin:16mm 17mm 17mm}
body{font-family:Inter,'Segoe UI',Arial,sans-serif;color:#1d1a16;font-size:10.5pt;line-height:1.5;margin:0}
h1{font-family:'Iowan Old Style','Palatino Linotype',Palatino,Caladea,Georgia,serif;font-size:24pt;line-height:1.08;margin:0 0 4pt}
h2{font-family:'Iowan Old Style','Palatino Linotype',Palatino,Caladea,Georgia,serif;font-size:14.5pt;color:#8a5a1c;margin:14pt 0 5pt;break-after:avoid}
h3{font-size:11pt;margin:10pt 0 3pt;break-after:avoid}p{margin:0 0 7pt}ul,ol{margin:0 0 8pt;padding-left:18pt}li{margin:0 0 3pt}
.sub{color:#5f574b;font-size:11.5pt;margin:0 0 10pt;padding-bottom:8pt;border-bottom:2px solid #c8a24a}
mark{background:#fff1b8;color:inherit;padding:0 2pt;border-radius:2pt}
.small{color:#5f574b;font-size:8.8pt}
.note,.warn,.email{border-radius:7pt;padding:8pt 11pt;margin:8pt 0;break-inside:avoid}
.note{background:#f6f2ea}.warn{background:#fdf1e7;border-left:4pt solid #9a3412}
.email{background:#fffdf9;border:1px solid #d8cfbf}.email .subj{font-weight:700;margin-bottom:5pt}
.check{list-style:none;padding-left:4pt}.check li:before{content:"\\2610\\00a0\\00a0";font-size:11pt}
table{border-collapse:collapse;width:100%;font-size:9.6pt;margin:4pt 0 9pt;break-inside:auto}td,th{border:1px solid #d8cfbf;padding:4pt 6pt;text-align:left;vertical-align:top}
th{background:#f1ece2}.fields td:first-child{width:38%;font-weight:700;background:#faf7f1}
.script p{margin:0 0 5pt}.script b{color:#8a5a1c}
.sign{display:grid;grid-template-columns:1fr 1fr;gap:16pt 28pt;margin:16pt 0 8pt}.sign div{border-top:1px solid #1d1a16;padding-top:3pt;font-size:9pt;color:#5f574b;margin-top:22pt}
.lines div{border-bottom:1px solid #d8cfbf;height:20pt}
.pb{break-before:page}"""


def to_html(doc: dict, css_extra: str = "") -> str:
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><style>{DOC_CSS}{css_extra}</style></head><body>",
           f"<h1>{_html.escape(doc['title'])}</h1>"]
    if doc.get("subtitle"):
        out.append(f"<p class='sub'>{inline_html(doc['subtitle'])}</p>")
    pb = False
    for b in doc["blocks"]:
        k = b[0]
        cls = " class='pb'" if pb and k in ("h1", "h2") else ""
        pb = False
        if k in ("h1", "h2", "h3"):
            out.append(f"<{k}{cls}>{inline_html(b[1])}</{k}>")
        elif k == "p":
            out.append(f"<p>{inline_html(b[1])}</p>")
        elif k == "small":
            out.append(f"<p class='small'>{inline_html(b[1])}</p>")
        elif k in ("ul", "ol", "check"):
            tag = "ol" if k == "ol" else "ul"
            out.append(f"<{tag}{' class=check' if k == 'check' else ''}>" + "".join(f"<li>{inline_html(x)}</li>" for x in b[1]) + f"</{tag}>")
        elif k == "table":
            cols = "".join(f'<col style="width:{100 * w / sum(b[3]):.0f}%">' for w in b[3]) if len(b) > 3 else ""
            out.append(f"<table><colgroup>{cols}</colgroup><tr>" + "".join(f"<th>{inline_html(h)}</th>" for h in b[1]) + "</tr>" +
                       "".join("<tr>" + "".join(f"<td>{inline_html(str(c))}</td>" for c in r) + "</tr>" for r in b[2]) + "</table>")
        elif k in ("note", "warn"):
            out.append(f"<div class='{k}'>{inline_html(b[1])}</div>")
        elif k == "email":
            out.append(f"<div class='email'><div class='subj'>Subject: {inline_html(b[1])}</div>{inline_html(b[2])}</div>")
        elif k == "script":
            out.append("<div class='script'>" + "".join(f"<p><b>{_html.escape(w)}:</b> {inline_html(t)}</p>" for w, t in b[1]) + "</div>")
        elif k == "fields":
            out.append("<table class='fields'>" + "".join(f"<tr><td>{inline_html(a)}</td><td>{inline_html(h)}</td></tr>" for a, h in b[1]) + "</table>")
        elif k == "sign":
            out.append("<div class='sign'>" + "".join(f"<div>{_html.escape(x)}</div>" for x in b[1]) + "</div>")
        elif k == "lines":
            out.append("<div class='lines'>" + "<div></div>" * b[1] + "</div>")
        elif k == "pagebreak":
            pb = True
    if doc.get("footer"):
        out.append(f"<p class='small' style='margin-top:14pt'>{inline_html(doc['footer'])}</p>")
    out.append("</body></html>")
    return "".join(out)


# ------------------------------------------------------------------------------------------------ DOCX
def to_docx(doc: dict, path: str) -> str:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_COLOR_INDEX
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    d = Document()
    sec = d.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Inches(0.9))
    sec.top_margin, sec.bottom_margin = Inches(0.85), Inches(0.85)
    st = d.styles
    st["Normal"].font.name = "Arial"
    st["Normal"].font.size = Pt(10.5)
    st["Normal"].font.color.rgb = RGBColor.from_string(INK)
    st["Normal"].paragraph_format.space_after = Pt(6)
    st["Normal"].paragraph_format.line_spacing = 1.15
    for name, size, color, font in (("Title", 24, INK, "Georgia"), ("Heading 1", 18, INK, "Georgia"), ("Heading 2", 14, ACCENT, "Georgia"), ("Heading 3", 11.5, INK, "Arial")):
        s = st[name]
        s.font.name, s.font.size, s.font.bold, s.font.color.rgb = font, Pt(size), True, RGBColor.from_string(color)
        s.paragraph_format.space_before, s.paragraph_format.space_after = Pt(12 if name != "Title" else 0), Pt(4)
        rpr = s.element.get_or_add_rPr()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            rpr.append(fonts)
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            fonts.set(qn(a), font)
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if fonts.get(qn(a)) is not None:
                del fonts.attrib[qn(a)]

    def shade(cell, hexcolor):
        tcpr = cell._tc.get_or_add_tcPr()
        sh = OxmlElement("w:shd")
        sh.set(qn("w:val"), "clear")
        sh.set(qn("w:color"), "auto")
        sh.set(qn("w:fill"), hexcolor)
        tcpr.append(sh)

    def borders(table, color=LINE):
        tblpr = table._tbl.tblPr
        b = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement(f"w:{edge}")
            e.set(qn("w:val"), "single")
            e.set(qn("w:sz"), "6")
            e.set(qn("w:color"), color)
            b.append(e)
        tblpr.append(b)

    def add_runs(p, text, size=None, color=None, bold=False, italic=False):
        for t, kind in _runs(text):
            parts = t.split("\n")
            for i, piece in enumerate(parts):
                r = p.add_run(piece)
                r.bold = bold or kind == "b"
                r.italic = italic
                if size:
                    r.font.size = Pt(size)
                if color:
                    r.font.color.rgb = RGBColor.from_string(color)
                if kind == "fill":
                    r.font.highlight_color = WD_COLOR_INDEX.YELLOW
                if i < len(parts) - 1:
                    r.add_break()
        return p

    def para(text, style=None, **kw):
        p = d.add_paragraph(style=style)
        return add_runs(p, text, **kw)

    def box(fill, fn):
        t = d.add_table(rows=1, cols=1)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        borders(t, "E2D9C8" if fill != WARN else "E8B9A0")
        c = t.cell(0, 0)
        shade(c, fill)
        trpr = t.rows[0]._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit")
        trpr.append(cs)
        c.paragraphs[0].text = ""
        fn(c)
        d.add_paragraph().paragraph_format.space_after = Pt(2)

    title = d.add_paragraph(style="Title")
    add_runs(title, doc["title"])
    if doc.get("subtitle"):
        para(doc["subtitle"], size=11.5, color=MUTED)
    page_break_next = False
    for b in doc["blocks"]:
        k = b[0]
        if k in ("h1", "h2", "h3"):
            p = d.add_paragraph(style={"h1": "Heading 1", "h2": "Heading 2", "h3": "Heading 3"}[k])
            add_runs(p, b[1])
            if page_break_next:
                p.paragraph_format.page_break_before = True
        elif k == "p":
            para(b[1])
        elif k == "small":
            para(b[1], size=9, color=MUTED)
        elif k in ("ul", "ol", "check"):
            for i, x in enumerate(b[1], 1):
                lead = {"ul": "•  ", "ol": f"{i}.  ", "check": "☐  "}[k]
                p = d.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.3)
                p.paragraph_format.first_line_indent = Inches(-0.22)
                p.paragraph_format.space_after = Pt(3)
                p.add_run(lead).bold = k == "ol"
                add_runs(p, x)
        elif k == "table":
            t = d.add_table(rows=1, cols=len(b[1]))
            borders(t)
            widths = b[3] if len(b) > 3 else None
            if widths:
                t.autofit = False
            hdr = t.rows[0]._tr.get_or_add_trPr()
            hdr.append(OxmlElement("w:tblHeader"))          # the header row repeats when a table runs onto the next page
            for j, h in enumerate(b[1]):
                c = t.rows[0].cells[j]
                c.paragraphs[0].text = ""
                add_runs(c.paragraphs[0], h, bold=True)
                shade(c, "F1ECE2")
            for row in b[2]:
                r = t.add_row()
                r._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
                for j, v in enumerate(row):
                    r.cells[j].paragraphs[0].text = ""
                    add_runs(r.cells[j].paragraphs[0], str(v))
            if widths:
                for j, w in enumerate(widths):
                    t.columns[j].width = Inches(w)               # the grid (what most apps read)
                for r in t.rows:
                    for j, w in enumerate(widths):
                        r.cells[j].width = Inches(w)             # and each cell (what the others read)
            d.add_paragraph().paragraph_format.space_after = Pt(2)
        elif k in ("note", "warn"):
            box(SOFT if k == "note" else WARN, lambda c, t=b[1]: add_runs(c.paragraphs[0], t))
        elif k == "email":
            def fill_email(c, s=b[1], body=b[2]):
                add_runs(c.paragraphs[0], "Subject: " + s, bold=True)
                add_runs(c.add_paragraph(), body)
            box("FFFDF9", fill_email)
        elif k == "script":
            for who, line in b[1]:
                p = d.add_paragraph()
                r = p.add_run(who + ": ")
                r.bold = True
                r.font.color.rgb = RGBColor.from_string(ACCENT)
                add_runs(p, line)
        elif k == "fields":
            t = d.add_table(rows=0, cols=2)
            borders(t)
            for label, hint in b[1]:
                cells = t.add_row().cells
                cells[0].paragraphs[0].text = ""
                add_runs(cells[0].paragraphs[0], label, bold=True)
                shade(cells[0], "FAF7F1")
                cells[1].paragraphs[0].text = ""
                add_runs(cells[1].paragraphs[0], hint)
                cells[0].width, cells[1].width = Inches(2.6), Inches(4.1)
            d.add_paragraph().paragraph_format.space_after = Pt(2)
        elif k == "sign":
            t = d.add_table(rows=0, cols=2)
            labels = list(b[1])
            for i in range(0, len(labels), 2):
                cells = t.add_row().cells
                for j, lab in enumerate(labels[i:i + 2]):
                    c = cells[j]
                    c.paragraphs[0].text = ""
                    c.paragraphs[0].paragraph_format.space_before = Pt(26)
                    c.paragraphs[0].add_run("_" * 38)
                    add_runs(c.add_paragraph(), lab, size=9, color=MUTED)
            d.add_paragraph()
        elif k == "lines":
            for _ in range(b[1]):
                d.add_paragraph("_" * 86).runs[0].font.color.rgb = RGBColor.from_string("BFB5A3")
        elif k == "pagebreak":
            page_break_next = True
            continue
        page_break_next = False if k in ("h1", "h2", "h3") else page_break_next
    if doc.get("footer"):
        para(doc["footer"], size=9, color=MUTED)
    # header and page numbers
    hp = sec.header.paragraphs[0]
    hp.text = ""
    r = hp.add_run(doc.get("header") or doc["title"])
    r.font.size, r.font.color.rgb = Pt(8.5), RGBColor.from_string("8C8273")
    fp = sec.footer.paragraphs[0]
    fp.text = ""
    r = fp.add_run("Page ")
    r.font.size = Pt(8.5)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    rr = OxmlElement("w:r")
    tt = OxmlElement("w:t")
    tt.text = "1"
    rr.append(tt)
    fld.append(rr)
    fp._p.append(fld)
    d.save(path)
    return path


def text_of(doc: dict) -> str:
    """Plain text of a document (for the tests' word checks)."""
    parts = [doc["title"], doc.get("subtitle", ""), doc.get("footer", "")]
    for b in doc["blocks"]:
        for x in b[1:]:
            if isinstance(x, str):
                parts.append(x)
            elif isinstance(x, (list, tuple)):
                for y in x:
                    parts.append(" ".join(map(str, y)) if isinstance(y, (list, tuple)) else str(y))
    return "\n".join(parts)
