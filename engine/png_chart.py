"""Premium card PNGs for Telegram (night-nq-cards 2026-11-27; first version day-cards 2026-11-26): numpy + zlib only, so the PC
needs no new package (matplotlib is only in requirements-cloud.txt). OLYMPUS NIGHT look: black, a #16131e card with a violet
outline + glow, gold accents, mint up / rose down. Anti-aliased (exact pixel coverage) candles, a smooth glowing price line,
entry / stop / target / sweep lines with name + price tags, shaded risk / reward zones, a header (bot, account, side, R, $) in a
crisp bitmap font (engine/png_font). 1280 x 720 = Telegram's own photo size (retina on a phone), well under 300 KB.
Read-only, pure, never raises out of a render function (None = draw nothing: the caller sends the text message).

    render(bars, lines, marks, w=1280, h=720, head=None, foot="", zones=()) -> PNG bytes | None      the trade card
      bars   [(t, open, high, low, close)]
      lines  [(price, (r, g, b), t_from or None, dashed bool[, label])]
      marks  [(t, price, (r, g, b)[, "entry" | "exit"])]
      head   {"bot", "account", "side", "qty", "hero", "hero_col", "sub", "tag"}   zones [(p_a, p_b, t_from, (r, g, b))]
    render_day(spec) -> PNG bytes | None      the 16:20 (half day: halt + 20 min) day summary
    render_week(spec) -> PNG bytes | None     the Friday week report
"""
from __future__ import annotations

import datetime as _dt
import struct
import zlib

import numpy as np

from . import png_font as F

BG = (0, 0, 0)
CARD = (22, 19, 30)             # #16131e
CARD2 = (30, 25, 42)
EDGE = (62, 37, 94)             # #3e255e
EDGE2 = (77, 46, 118)           # #4d2e76
GLOW = (157, 89, 238)           # #9d59ee
GRID = (38, 31, 52)
MUTED = (140, 128, 163)
SOFT = (196, 186, 214)
UP = (119, 219, 137)            # mint #77db89
DOWN = (255, 93, 115)           # rose (stops / losses; never brown)
WHITE = (240, 238, 245)
GOLD = (241, 193, 75)           # #f1c14b
RED = DOWN
GREEN = UP
VIOLET = GLOW
LILAC = (201, 163, 255)
BLUE = WHITE                    # the old exit mark colour name: now a white ring (no cyan in the Olympus look)
INK = (12, 9, 18)
W0, H0 = 1280, 720
LEVEL = 4                       # zlib level 4: ~2.5x faster than 6 for ~7% more bytes (a noisy 6 h chart ~190 KB)


# ------------------------------------------------------------------------------------------------ the PNG file
def _png(img: np.ndarray) -> bytes:
    """RGB uint8 -> PNG. Filter 2 (Up) on every row: the flat card / gradients become zeros, so the file stays small."""
    h, w, _ = img.shape
    up = img.copy()
    up[1:] = img[1:] - img[:-1]                       # uint8 wraps mod 256 = the PNG Up filter
    raw = np.empty((h, w * 3 + 1), np.uint8)
    raw[:, 0] = 2
    raw[0, 0] = 0
    raw[0, 1:] = img[0].reshape(-1)
    raw[1:, 1:] = up[1:].reshape(h - 1, -1)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw.tobytes(), LEVEL)) + chunk(b"IEND", b""))


def _blur(m: np.ndarray, r: int) -> np.ndarray:
    """A cheap soft blur (two box passes per axis) for glows."""
    if r < 1:
        return m
    for ax in (0, 1, 0, 1):
        p = np.pad(m, [((r + 1, r) if a == ax else (0, 0)) for a in range(2)], mode="constant")
        c = np.cumsum(p, axis=ax, dtype=np.float32)
        if ax == 0:
            m = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
        else:
            m = (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)
    return m


class Canvas:
    """A float RGB canvas; every shape blends by exact pixel coverage (anti-aliased)."""

    def __init__(self, w: int, h: int, bg=BG):
        self.w, self.h = int(w), int(h)
        self.a = np.empty((self.h, self.w, 3), np.float32)
        self.a[:] = bg

    def blend(self, x0: int, y0: int, m: np.ndarray, col, alpha: float = 1.0):
        hh, ww = m.shape
        if m.size > 4096 and m.min() == 1.0 and alpha == 1.0:      # a solid block: plain assignment
            xa, ya, xb, yb = max(0, x0), max(0, y0), min(self.w, x0 + ww), min(self.h, y0 + hh)
            if xa < xb and ya < yb:
                self.a[ya:yb, xa:xb] = col
            return
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(self.w, x0 + ww), min(self.h, y0 + hh)
        if xa >= xb or ya >= yb:
            return
        mm = m[ya - y0:yb - y0, xa - x0:xb - x0]
        if alpha != 1.0:
            mm = mm * alpha
        r = self.a[ya:yb, xa:xb]
        r += (np.asarray(col, np.float32) - r) * mm[..., None]

    @staticmethod
    def _cov(a: float, b: float):
        i0, i1 = int(np.floor(a)), int(np.ceil(b))
        xs = np.arange(i0, i1, dtype=np.float32)
        return i0, np.clip(np.minimum(b, xs + 1) - np.maximum(a, xs), 0, 1)

    def rect(self, x0, y0, x1, y1, col, alpha=1.0, xpat=None):
        if x1 <= x0 or y1 <= y0:
            return
        ix, cx = self._cov(x0, x1)
        iy, cy = self._cov(y0, y1)
        if xpat is not None:
            cx = cx * xpat(np.arange(ix, ix + len(cx)))
        self.blend(ix, iy, np.outer(cy, cx), col, alpha)

    def hline(self, xa, xb, y, col, lw=2.0, alpha=1.0, dash=None):
        pat = None
        if dash:
            on, off = dash
            pat = lambda xs: (((xs - int(xa)) % (on + off)) < on).astype(np.float32)   # noqa: E731
        self.rect(xa, y - lw / 2, xb, y + lw / 2, col, alpha, pat)

    def _sdf(self, x0, y0, x1, y1, r, bx0, by0, bx1, by1):
        px = np.arange(bx0, bx1, dtype=np.float32) + 0.5
        py = np.arange(by0, by1, dtype=np.float32) + 0.5
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        hx, hy = (x1 - x0) / 2 - r, (y1 - y0) / 2 - r
        qx = (np.abs(px - cx) - hx)[None, :]
        qy = (np.abs(py - cy) - hy)[:, None]
        return np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - r

    def rrect(self, x0, y0, x1, y1, r, fill=None, alpha=1.0, line=None, lw=1.5, glow=None, glow_r=14.0, glow_a=0.45):
        r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
        pad = glow_r * 3 if glow else 2
        bx0, by0 = max(0, int(np.floor(x0 - pad))), max(0, int(np.floor(y0 - pad)))
        bx1, by1 = min(self.w, int(np.ceil(x1 + pad))), min(self.h, int(np.ceil(y1 + pad)))
        e = int(np.ceil(max(r, lw) + 2))                  # the border band; the inside is a plain fill (fast on big cards)
        ix0, iy0, ix1, iy1 = int(np.ceil(x0)) + e, int(np.ceil(y0)) + e, int(np.floor(x1)) - e, int(np.floor(y1)) - e
        if ix1 - ix0 > 8 and iy1 - iy0 > 8:
            boxes = [(bx0, by0, bx1, iy0), (bx0, iy1, bx1, by1), (bx0, iy0, ix0, iy1), (ix1, iy0, bx1, iy1)]
            if fill is not None:
                self.blend(ix0, iy0, np.ones((iy1 - iy0, ix1 - ix0), np.float32), fill, alpha)
        else:
            boxes = [(bx0, by0, bx1, by1)]
        for ax0, ay0, ax1, ay1 in boxes:
            if ax1 <= ax0 or ay1 <= ay0:
                continue
            d = self._sdf(x0, y0, x1, y1, r, ax0, ay0, ax1, ay1)
            if glow:
                self.blend(ax0, ay0, np.where(d > 0, np.exp(-d / glow_r), 0).astype(np.float32), glow, glow_a)
            if fill is not None:
                self.blend(ax0, ay0, np.clip(0.5 - d, 0, 1), fill, alpha)
            if line is not None:
                self.blend(ax0, ay0, np.clip(lw / 2 + 0.5 - np.abs(d + lw / 2), 0, 1), line)

    def circle(self, cx, cy, r, col, alpha=1.0, ring=0.0, glow=None, glow_r=6.0):
        pad = r + (glow_r * 3 if glow else 2)
        x0, y0 = int(np.floor(cx - pad)), int(np.floor(cy - pad))
        n = int(np.ceil(2 * pad)) + 1
        px = np.arange(x0, x0 + n, dtype=np.float32) + 0.5
        py = np.arange(y0, y0 + n, dtype=np.float32) + 0.5
        d = np.sqrt((px[None, :] - cx) ** 2 + (py[:, None] - cy) ** 2) - r
        if glow:
            self.blend(x0, y0, np.exp(-np.maximum(d, 0) / glow_r) * 0.55, glow)
        m = np.clip(ring / 2 + 0.5 - np.abs(d + ring / 2), 0, 1) if ring else np.clip(0.5 - d, 0, 1)
        self.blend(x0, y0, m.astype(np.float32), col, alpha)

    def text(self, x, y, s, scale=2, col=WHITE, alpha=1.0, anchor="l", glow=None, max_px=None):
        """Bitmap text, top-left at (x, y) (anchor "r" = right edge at x, "c" = centred). Returns the width drawn."""
        s = F.fit(s, max_px, scale) if max_px else F.norm(s)
        m = F.mask(s)
        if m.shape[1] == 0:
            return 0
        sc = int(scale)
        m = np.kron(m, np.ones((sc, sc), np.float32))
        wpx = m.shape[1]
        x = int(round(x - (wpx if anchor == "r" else wpx / 2 if anchor == "c" else 0)))
        y = int(round(y))
        if glow:
            g = max(2, sc * 2)
            gm = _blur(np.pad(m, g * 2), g)
            self.blend(x - g * 2, y - g * 2, np.clip(gm * 1.6, 0, 1), glow, 0.5)
        self.blend(x, y, m, col, alpha)
        return wpx

    def pill(self, x, y, s, scale=2, fg=INK, bg=GOLD, pad=8, anchor="l", alpha=1.0):
        """A rounded tag with text; (x, y) = its top-left (anchor "r": right edge). Returns (x0, x1)."""
        tw = F.width(s, scale)
        hh = 7 * scale + pad
        ww = tw + pad * 2
        x0 = x - ww if anchor == "r" else x
        self.rrect(x0, y, x0 + ww, y + hh, hh / 2, fill=bg, alpha=alpha)
        self.text(x0 + pad, y + pad / 2, s, scale, fg)
        return x0, x0 + ww

    def png(self) -> bytes:
        return _png(np.clip(self.a + 0.5, 0, 255).astype(np.uint8))


# ------------------------------------------------------------------------------------------------ shared pieces
def money(v, signed=True) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "-"
    s = f"${abs(v):,.0f}"
    return (("+" if v > 0 else "-" if v < 0 else "") + s) if signed else s


def col_of(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return SOFT
    return UP if v > 0 else DOWN if v < 0 else SOFT


_BASE: dict = {}


def _base(w: int, h: int, plot=None) -> np.ndarray:
    """The static page (black, the card, its violet outline + glow, the plot box), drawn once per size and copied after."""
    k = (w, h, plot)
    if k not in _BASE:
        c = Canvas(w, h)
        c.rrect(22, 22, w - 22, h - 22, 24, fill=CARD, line=EDGE2, lw=2.0, glow=GLOW, glow_r=10, glow_a=0.55)
        if plot:
            x0, y0, x1, y1 = plot
            c.rrect(x0, y0, x1, y1, 14, fill=(14, 11, 20), line=EDGE, lw=1.0)
        if len(_BASE) > 8:
            _BASE.clear()
        _BASE[k] = c.a
    return _BASE[k]


def _frame(c: Canvas, top_label: str, right_tag: str = "", plot=None):
    """The black page, the violet-outlined card with its glow, the gold OLYMPUS mark."""
    c.a[:] = _base(c.w, c.h, plot)
    c.circle(54, 52, 7, GOLD, glow=GOLD, glow_r=5)
    x = 70 + c.text(70, 45, "OLYMPUS", 2, GOLD)
    c.text(x + 12, 45, top_label, 2, LILAC)
    if right_tag:
        c.text(c.w - 52, 45, right_tag, 2, MUTED, anchor="r")


def _et(t):
    try:
        from zoneinfo import ZoneInfo
        return _dt.datetime.fromtimestamp(int(t), ZoneInfo("America/New_York"))
    except Exception:
        return _dt.datetime.utcfromtimestamp(int(t))


def _smooth(xs, ys, k=4):
    """Catmull-Rom through the points, k samples per segment."""
    xs, ys = np.asarray(xs, np.float32), np.asarray(ys, np.float32)
    if len(xs) < 3:
        return xs, ys
    P = np.stack([xs, ys], 1)
    P = np.vstack([P[:1], P, P[-1:]])
    t = np.linspace(0, 1, k, endpoint=False, dtype=np.float32)[:, None]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2:-1])
    Q = np.vstack(out)
    return Q[:, 0], Q[:, 1]


def _curve(c: Canvas, xs, ys, x0, x1, y0, y1, col, lw=2.6, fill_a=0.16, glow_a=0.35):
    """A smooth glowing line through (xs, ys) with a fading violet ribbon under it; clipped to the plot box."""
    sx, sy = _smooth(xs, ys)
    xa, xb = max(int(np.floor(sx.min())), int(x0)), min(int(np.ceil(sx.max())) + 1, int(x1))
    if xb - xa < 2:
        return
    px = np.arange(xa, xb, dtype=np.float32) + 0.5
    yc = np.interp(px, sx, sy).astype(np.float32)
    slope = np.gradient(yc)
    k = np.sqrt(1 + slope ** 2)
    ya, yb = int(y0), int(y1)
    py = (np.arange(ya, yb, dtype=np.float32) + 0.5)[:, None]
    dy = py - yc[None, :]
    d = np.abs(dy) / k[None, :]
    keep = 1 - np.clip(lw / 2 + 0.5 - d, 0, 1)                       # 1 - coverage, multiplied: one blend for all three
    if glow_a:
        keep *= 1 - np.exp(-(d / 7.0) ** 2) * glow_a
    if fill_a:
        keep *= 1 - np.clip(dy + 0.5, 0, 1) * np.clip(1 - dy / 200.0, 0, 1) ** 1.6 * fill_a
    c.blend(xa, ya, (1 - keep).astype(np.float32), col)


def _price(p) -> str:
    return f"{float(p):,.2f}"


# ------------------------------------------------------------------------------------------------ the trade card
def render(bars, lines=(), marks=(), w: int = W0, h: int = H0, head=None, foot: str = "", zones=()) -> bytes | None:
    """PNG bytes, or None when there is nothing to draw."""
    try:
        B = [(int(t), float(o), float(hi), float(lo), float(cl)) for t, o, hi, lo, cl in bars or []]
        if len(B) < 2:
            return None
        head = head or {}
        X0, X1, Y0, Y1 = 52.0, w - 250.0, 168.0, h - 96.0
        c = Canvas(w, h)
        _frame(c, str(head.get("bot") or "TRADE"), str(head.get("tag") or ""), (X0 - 8, Y0 - 10, X1 + 8, Y1 + 10))
        # ---- header
        c.text(52, 78, str(head.get("account") or ""), 4, WHITE, max_px=560)
        side = str(head.get("side") or "").upper()
        if side:
            sc = UP if side == "LONG" else DOWN
            lab = side + (f"  {int(head['qty'])} MNQ" if head.get("qty") else "")
            c.pill(52, 120, lab, 2, INK, sc, pad=8)
        if head.get("hero"):
            hc = head.get("hero_col") or GOLD
            c.text(w - 52, 66, str(head["hero"]), 7, hc, anchor="r", glow=hc)
        if head.get("sub"):
            c.text(w - 52, 124, str(head["sub"]), 2, SOFT, anchor="r", max_px=620)
        # ---- the plot box
        prices = [x for b in B for x in (b[2], b[3])] + [float(L[0]) for L in lines or [] if L[0] is not None]
        lo, hi = min(prices), max(prices)
        span = (hi - lo) or 1.0
        lo, hi = lo - span * 0.07, hi + span * 0.07
        n = len(B)
        t0 = B[0][0]
        step = max(1, (B[-1][0] - t0) / max(1, n - 1))
        cw = (X1 - X0) / n

        def y_of(p):
            return Y0 + (hi - float(p)) / (hi - lo) * (Y1 - Y0)

        def x_of(t):
            return X0 + ((float(t) - t0) / step + 0.5) * cw

        # grid + price axis
        raw = span / 5
        mag = 10 ** np.floor(np.log10(raw))
        stp = min((m * mag for m in (1, 2, 2.5, 5, 10)), key=lambda v: abs(v - raw))
        tags = []
        for L in lines or []:
            p, col, tf, dashed = L[0], L[1], L[2], L[3]
            lab = L[4] if len(L) > 4 else ""
            if p is None:
                continue
            y = y_of(p)
            if not Y0 - 2 <= y <= Y1 + 2:
                continue
            xa = max(X0, x_of(tf) - cw / 2) if tf else X0
            tags.append([y - 11, y, (f"{lab} " if lab else "") + _price(p), col, xa, dashed])
        tags.sort(key=lambda z: z[0])                     # spread the tags so close lines (stop / sweep) never overlap
        for i in range(1, len(tags)):
            tags[i][0] = max(tags[i][0], tags[i - 1][0] + 25)
        if tags and tags[-1][0] > Y1 + 4:
            tags[-1][0] = Y1 + 4
            for i in range(len(tags) - 2, -1, -1):
                tags[i][0] = min(tags[i][0], tags[i + 1][0] - 25)
        tags_y = [z[0] + 11 for z in tags]
        g = np.ceil(lo / stp) * stp
        while g <= hi:
            y = y_of(g)
            if Y0 + 4 < y < Y1 - 4:
                c.hline(X0, X1, y, GRID, 1.0)
                if all(abs(y - ty) > 16 for ty in tags_y):
                    c.text(X1 + 18, y - 7, f"{g:,.0f}" if stp >= 1 else f"{g:,.2f}", 2, MUTED)
            g += stp
        # time axis: a label every 30 / 60 min
        span_min = (B[-1][0] - t0) / 60
        every = 30 if span_min <= 240 else 60 if span_min <= 480 else 120
        for t, *_ in B:
            e = _et(t)
            if (e.hour * 60 + e.minute) % every == 0:
                x = x_of(t)
                c.rect(x - 0.5, Y0, x + 0.5, Y1, GRID, 0.6)
                c.text(x, Y1 + 18, f"{e:%H:%M}", 2, MUTED, anchor="c")
        c.text(X1 + 18, Y1 + 18, "TIMES ET", 2, MUTED)
        # zones (reward / risk boxes from the entry)
        for pa, pb, tf, zc in zones or []:
            if pa is None or pb is None:
                continue
            xa = max(X0, x_of(tf)) if tf else X0
            ya, yb = sorted((y_of(pa), y_of(pb)))
            c.rect(xa, max(Y0, ya), X1, min(Y1, yb), zc, 0.09)
        # candles
        bw = max(1.0, cw * 0.62)
        ww = max(1.0, min(2.0, cw * 0.22))
        for i, (t, o, hi_, lo_, cl) in enumerate(B):
            x = X0 + (i + 0.5) * cw
            col = UP if cl >= o else DOWN
            c.rect(x - ww / 2, y_of(hi_), x + ww / 2, y_of(lo_), col, 0.75)
            ya, yb = sorted((y_of(o), y_of(cl)))
            c.rect(x - bw / 2, ya, x + bw / 2, max(yb, ya + 1.2), col, 0.92)
        # the smooth price line (closes)
        _curve(c, [X0 + (i + 0.5) * cw for i in range(n)], [y_of(b[4]) for b in B], X0, X1, Y0, Y1, GLOW)
        # plan lines + their tags
        for ty, y, s_, col, xa, dashed in tags:
            c.hline(xa, X1, y, col, 2.0, 0.95, (10, 7) if dashed else None)
        for ty, y, s_, col, xa, dashed in tags:
            x0, _x1 = c.pill(w - 30, ty, s_, 2, INK, col, pad=8, anchor="r")
            if abs(ty + 11 - y) > 3:                      # a moved tag: a thin leader to its line
                c.rect(X1, y - 0.75, x0, y + 0.75, col, 0.7)
        # marks
        for M in marks or []:
            t, p, col = M[0], M[1], M[2]
            kind = M[3] if len(M) > 3 else "entry"
            if p is None:
                continue
            x, y = x_of(t), y_of(p)
            if kind == "exit":
                c.circle(x, y, 9, col, ring=3.0, glow=col)
                c.circle(x, y, 3, col)
            else:
                c.circle(x, y, 8, col, glow=col)
                c.circle(x, y, 3.2, INK)
        if foot:
            c.text(52, h - 52, foot, 2, SOFT, max_px=w - 104)
        return c.png()
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ the day summary
def _bar_meter(c, x, y, wpx, frac, col, h=10):
    c.rrect(x, y, x + wpx, y + h, h / 2, fill=GRID)
    f = max(0.0, min(1.0, float(frac)))
    if f > 0.001:
        c.rrect(x, y, x + max(h, wpx * f), y + h, h / 2, fill=col)


def _mini_bars(c, x0, y0, x1, y1, vals, labels, col_pos=UP, col_neg=DOWN, twin=None):
    """Bars around a zero line (+ an outlined twin bar each when given). vals may hold None (= no bar)."""
    allv = [abs(float(v)) for v in list(vals) + list(twin or []) if v is not None]
    top = max(allv) if allv else 1.0
    top = top or 1.0
    n = max(1, len(vals))
    zw = (x1 - x0) / n
    mid = (y0 + y1) / 2
    c.hline(x0, x1, mid, EDGE2, 1.0)
    half = (y1 - y0) / 2 - 4
    for i, v in enumerate(vals):
        cx = x0 + (i + 0.5) * zw
        bw = zw * (0.32 if twin else 0.5)
        if twin and twin[i] is not None:
            tv = float(twin[i])
            hh = abs(tv) / top * half
            ya, yb = (mid - hh, mid) if tv >= 0 else (mid, mid + hh)
            c.rrect(cx + 2, ya, cx + 2 + bw, max(yb, ya + 4), 3, line=GOLD, lw=2.0)
        if v is not None:
            fv = float(v)
            hh = abs(fv) / top * half
            ya, yb = (mid - hh, mid) if fv >= 0 else (mid, mid + hh)
            xa = cx - bw - 2 if twin else cx - bw / 2
            c.rrect(xa, ya, xa + bw, max(yb, ya + 2), 3, fill=col_pos if fv >= 0 else col_neg)
        if labels:
            c.text(cx, y1 + 8, labels[i], 2, MUTED, anchor="c")


def render_day(spec: dict) -> bytes | None:
    """spec {"date": "FRI NOV 27", "total", "rows": [{"name", "today", "week", "month", "trades", "to_pass", "room", "mll",
    "sim"}], "days": [(label, $) last trading days], "note", "tag"}."""
    try:
        rows = [r for r in (spec or {}).get("rows") or [] if isinstance(r, dict)][:5]
        w = W0
        h = max(520, 300 + 112 * len(rows) + (0 if not spec.get("note") else 40))
        c = Canvas(w, h)
        _frame(c, "DAY SUMMARY", str(spec.get("tag") or ""))
        c.text(52, 78, str(spec.get("date") or ""), 4, WHITE)
        c.text(52, 124, "ALL ACCOUNTS TODAY", 2, MUTED)
        tot = spec.get("total")
        c.text(52, 150, money(tot), 8, col_of(tot), glow=col_of(tot))
        days = [d for d in spec.get("days") or [] if isinstance(d, (list, tuple)) and len(d) == 2][-7:]
        if days:
            c.text(w - 52, 78, "LAST TRADING DAYS", 2, MUTED, anchor="r")
            _mini_bars(c, w - 52 - 420, 104, w - 52, 196, [d[1] for d in days], [str(d[0]) for d in days])
        y = 240
        for r in rows:
            c.rrect(44, y, w - 44, y + 98, 16, fill=CARD2, line=EDGE, lw=1.0)
            c.text(66, y + 16, str(r.get("name") or "")[:28], 3, WHITE, max_px=420)
            if r.get("sim"):
                c.pill(66 + min(420, F.width(str(r.get("name") or "")[:28], 3)) + 14, y + 13, "SIM", 2, INK, LILAC, pad=6)
            cols = (("TODAY", r.get("today")), ("WEEK", r.get("week")), ("MONTH", r.get("month")))
            x = 540
            for lab, v in cols:
                c.text(x, y + 16, lab, 2, MUTED)
                c.text(x, y + 38, money(v), 3, col_of(v))
                x += 170
            nt = r.get("trades")
            c.text(x, y + 16, "TRADES", 2, MUTED)
            c.text(x, y + 38, "-" if nt is None else str(int(nt)), 3, WHITE)
            room, mll = r.get("room"), r.get("mll")
            tp = r.get("to_pass")
            if room is not None and mll:
                fr = float(room) / float(mll)
                _bar_meter(c, 66, y + 64, 400, fr, UP if fr > 0.5 else GOLD if fr > 0.25 else DOWN)
                c.text(476, y + 66, f"ROOM {money(room, False)} OF {money(mll, False)}", 2, SOFT)
            if tp is not None:
                c.text(w - 66, y + 66, "TARGET REACHED" if float(tp) <= 0 else f"{money(tp, False)} TO PASS", 2,
                       UP if float(tp) <= 0 else GOLD, anchor="r")
            y += 112
        if spec.get("note"):
            c.text(52, y + 4, spec["note"], 2, SOFT, max_px=w - 104)
        return c.png()
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ the week report
def render_week(spec: dict) -> bytes | None:
    """spec {"title": "WEEK NOV 23 - NOV 27", "total", "rows": [{"name", "week"}], "bots": [{"name", "live", "twin",
    "missed", "extra", "wins_live", "wins_twin"}], "daily": [(label, live $ | None, twin $ | None)], "note"}."""
    try:
        rows = [r for r in (spec or {}).get("rows") or [] if isinstance(r, dict)][:5]
        bots = [b for b in (spec or {}).get("bots") or [] if isinstance(b, dict)][:3]
        w, h = W0, max(520, 236 + 46 * len(rows) + 8 + 86 * len(bots) + (80 if spec.get("note") else 30))
        c = Canvas(w, h)
        _frame(c, "WEEK REPORT", "FRIDAY CLOSE")
        c.text(52, 78, str(spec.get("title") or ""), 4, WHITE)
        c.text(52, 124, "ALL ACCOUNTS THIS WEEK", 2, MUTED)
        tot = spec.get("total")
        c.text(52, 150, money(tot), 8, col_of(tot), glow=col_of(tot))
        daily = [d for d in spec.get("daily") or [] if isinstance(d, (list, tuple)) and len(d) == 3]
        if daily:
            c.text(w - 52, 78, "LIVE", 2, GLOW, anchor="r")
            c.text(w - 52 - F.width("LIVE", 2) - 16, 78, "BACKTEST", 2, GOLD, anchor="r")
            _mini_bars(c, w - 52 - 460, 104, w - 52, 196, [d[1] for d in daily], [str(d[0]) for d in daily],
                       col_pos=GLOW, col_neg=DOWN, twin=[d[2] for d in daily])
        y = 236
        top = max([abs(float(r.get("week") or 0)) for r in rows] + [1.0])
        for r in rows:
            v = r.get("week")
            c.text(66, y + 6, str(r.get("name") or "")[:28], 3, WHITE, max_px=380)
            mid = 760
            fv = float(v or 0)
            ln = abs(fv) / top * 300
            if fv >= 0:
                c.rrect(mid, y + 6, mid + max(4, ln), y + 26, 6, fill=UP)
            else:
                c.rrect(mid - max(4, ln), y + 6, mid, y + 26, 6, fill=DOWN)
            c.rect(mid - 0.75, y, mid + 0.75, y + 32, EDGE2)
            c.text(w - 66, y + 6, money(v), 3, col_of(v), anchor="r")
            y += 46
        y += 8
        for b in bots:
            c.rrect(44, y, w - 44, y + 72, 14, fill=CARD2, line=EDGE, lw=1.0)
            c.text(66, y + 14, str(b.get("name") or ""), 3, LILAC)
            line = f"{int(b.get('live') or 0)} LIVE VS {int(b.get('twin') or 0)} BACKTEST"
            if b.get("missed"):
                line += f" · {int(b['missed'])} MISSED"
            if b.get("extra"):
                line += f" · {int(b['extra'])} EXTRA"
            c.text(66, y + 44, line, 2, SOFT)
            wl = f"WINNERS {int(b.get('wins_live') or 0)}/{int(b.get('live') or 0)} LIVE"
            wt = f"{int(b.get('wins_twin') or 0)}/{int(b.get('twin') or 0)} BACKTEST"
            c.text(w - 66, y + 14, wl, 2, GLOW, anchor="r")
            c.text(w - 66, y + 40, wt, 2, GOLD, anchor="r")
            y += 86
        if spec.get("note"):
            c.text(52, h - 56, spec["note"], 2, SOFT, max_px=w - 104)
        return c.png()
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ the Insta card (day-insta 2026-11-27)
IW, IH = 1080, 1350             # Instagram's portrait post (4:5)


def render_insta(spec: dict) -> bytes | None:
    """The green-day share card, 1080 x 1350 (owner 2026-11-27: "a sick image to post on insta that shows daily PNL").
    spec {"date": "FRI NOV 27", "total", "rows": [{"name", "today"}] (names only), "trades", "wins", "losses",
          "bars": [(t, close)], "marks": [{"t", "px", "xt", "xpx", "usd"}]}. None on any trouble (no picture)."""
    try:
        w, h = IW, IH
        c = Canvas(w, h)
        c.a[:] = _base(w, h, (60, 520, w - 60, 930))
        # header: the brand + the date
        c.circle(76, 84, 9, GOLD, glow=GOLD, glow_r=7)
        x = 96 + c.text(96, 74, "OLYMPUS", 3, GOLD, glow=GOLD)
        c.text(x + 16, 74, "\u00b7 NQ", 3, LILAC)
        c.text(w - 64, 74, str(spec.get("date") or ""), 3, SOFT, anchor="r")
        # the hero: the day's $
        tot = spec.get("total")
        c.text(w / 2, 168, "DAY P&L", 3, MUTED, anchor="c")
        big = money(tot)
        sc = 20 if F.width(big, 20) <= w - 140 else max(8, int((w - 140) / max(1, F.width(big, 1))))
        c.text(w / 2, 222, big, sc, col_of(tot), anchor="c", glow=col_of(tot))
        # trades + win dots
        n, wins, losses = int(spec.get("trades") or 0), int(spec.get("wins") or 0), int(spec.get("losses") or 0)
        y = 222 + 7 * sc + 46
        line = f"{n} TRADE{'S' if n != 1 else ''}" + (f"  \u00b7  {wins} WIN{'S' if wins != 1 else ''}" if n else "")
        lw = c.text(w / 2, y, line, 3, WHITE, anchor="c")
        dots = ([UP] * wins + [DOWN] * losses)[:12]
        if dots:
            dx0 = w / 2 - (len(dots) - 1) * 30 / 2
            for i, col in enumerate(dots):
                c.circle(dx0 + i * 30, y + 64, 10, col, glow=col, glow_r=6)
        # the day's chart: the price line + every trade's entry (gold) and exit (white ring), the move between them
        bars = [b for b in spec.get("bars") or [] if isinstance(b, (list, tuple)) and len(b) >= 2]
        x0, y0, x1, y1 = 60 + 24, 520 + 30, w - 60 - 24, 930 - 30
        if len(bars) >= 2:
            ts = np.array([float(b[0]) for b in bars]); ps = np.array([float(b[1]) for b in bars])
            mk = [m for m in spec.get("marks") or [] if isinstance(m, dict)]
            allp = list(ps) + [float(m[k]) for m in mk for k in ("px", "xpx") if m.get(k) is not None]
            lo, hi = min(allp), max(allp)
            pad = (hi - lo) * 0.08 or 1.0
            lo, hi = lo - pad, hi + pad
            t0, t1 = float(ts.min()), float(ts.max()) or float(ts.min()) + 1
            fx = lambda t: x0 + (float(t) - t0) / max(1.0, t1 - t0) * (x1 - x0)
            fy = lambda p: y1 - (float(p) - lo) / max(1e-9, hi - lo) * (y1 - y0)
            for k in range(1, 4):
                c.hline(x0, x1, y0 + (y1 - y0) * k / 4, GRID, lw=1.0, alpha=0.8)
            _curve(c, [fx(t) for t in ts], [fy(p) for p in ps], x0, x1, y0, y1, VIOLET, lw=3.0, fill_a=0.18, glow_a=0.4)
            for m in mk:
                if m.get("t") is None or m.get("px") is None:
                    continue
                ex, ey = fx(min(max(m["t"], t0), t1)), fy(m["px"])
                if m.get("xt") is not None and m.get("xpx") is not None:
                    xx, xy = fx(min(max(m["xt"], t0), t1)), fy(m["xpx"])
                    col = col_of(m.get("usd"))
                    steps = max(2, int(abs(xx - ex) + abs(xy - ey)) // 3)
                    for i in range(steps + 1):
                        f = i / steps
                        c.circle(ex + (xx - ex) * f, ey + (xy - ey) * f, 2.2, col, alpha=0.9)
                    c.circle(xx, xy, 11, WHITE, ring=3.0, glow=col, glow_r=6)
                c.circle(ex, ey, 10, GOLD, glow=GOLD, glow_r=7)
            c.text(x0, 930 - 26, _et(t0).strftime("%H:%M"), 2, MUTED)
            c.text(x1, 930 - 26, _et(t1).strftime("%H:%M") + " ET", 2, MUTED, anchor="r")
        else:
            c.text(w / 2, 712, "THE CHART COMES WITH THE NEXT REPORT", 2, MUTED, anchor="c")
        # per account, names only
        rows = [r for r in spec.get("rows") or [] if isinstance(r, dict)][:4]
        y = 966
        for r in rows:
            c.rrect(60, y, w - 60, y + 66, 16, fill=CARD2, line=EDGE, lw=1.0)
            c.text(88, y + 23, str(r.get("name") or "")[:24], 3, WHITE, max_px=560)
            c.text(w - 88, y + 23, money(r.get("today")), 3, col_of(r.get("today")), anchor="r")
            y += 80
        # the brand
        c.hline(w / 2 - 160, w / 2 + 160, h - 112, EDGE2, lw=2.0)
        c.text(w / 2, h - 92, "OLYMPUS \u00b7 NQ", 4, GOLD, anchor="c", glow=GOLD)
        c.text(w / 2, h - 50, "FUTURES \u00b7 PROP EVAL", 2, MUTED, anchor="c")
        return c.png()
    except Exception:
        return None
