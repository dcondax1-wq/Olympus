"""A tiny candle-chart PNG renderer (day-cards 2026-11-26): numpy + zlib only, so the PC needs no new package (matplotlib is only
in requirements-cloud.txt). Draws 1-minute candles, horizontal plan lines (entry / stop / target / sweep level) from their start
time, and markers (entry, exit). No text: the Telegram caption names the colours. Read-only, pure, never raises out of render().

    render(bars, lines, marks, w=800, h=450) -> PNG bytes
      bars   [(t, open, high, low, close)]
      lines  [(price, (r, g, b), t_from or None, dashed bool)]
      marks  [(t, price, (r, g, b))]
"""
from __future__ import annotations

import struct
import zlib

import numpy as np

BG = (0, 0, 0)
GRID = (28, 24, 38)
UP = (119, 219, 137)            # mint (Olympus)
DOWN = (231, 96, 96)
WHITE = (235, 235, 235)
GOLD = (241, 193, 75)
RED = (240, 70, 70)
GREEN = (80, 220, 120)
VIOLET = (157, 89, 238)
BLUE = (90, 170, 255)


def _png(img: np.ndarray) -> bytes:
    h, w, _ = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def render(bars, lines=(), marks=(), w: int = 800, h: int = 450) -> bytes | None:
    """PNG bytes, or None when there is nothing to draw."""
    try:
        B = [(int(t), float(o), float(hi), float(lo), float(c)) for t, o, hi, lo, c in bars or []]
        if len(B) < 2:
            return None
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:, :] = BG
        pad_l, pad_r, pad_t, pad_b = 10, 10, 12, 12
        prices = [x for b in B for x in (b[2], b[3])] + [float(p) for p, *_ in lines or [] if p is not None]
        lo, hi = min(prices), max(prices)
        span = (hi - lo) or 1.0
        lo, hi = lo - span * 0.06, hi + span * 0.06
        t0, t1 = B[0][0], B[-1][0]
        n = len(B)
        cw = (w - pad_l - pad_r) / n

        def y_of(p):
            return int(round(pad_t + (hi - float(p)) / (hi - lo) * (h - pad_t - pad_b)))

        def x_of(t):
            if t1 == t0:
                return pad_l
            i = (float(t) - t0) / ((t1 - t0) / max(1, n - 1))
            return int(round(pad_l + (i + 0.5) * cw))

        for k in range(1, 6):                                    # a faint grid
            img[int(pad_t + k * (h - pad_t - pad_b) / 6), :] = GRID
        for i, (t, o, hi_, lo_, c) in enumerate(B):
            x = int(pad_l + (i + 0.5) * cw)
            col = UP if c >= o else DOWN
            ya, yb = sorted((y_of(hi_), y_of(lo_)))
            img[max(0, ya):min(h, yb + 1), max(0, x):min(w, x + 1)] = col
            bw = max(1, int(cw * 0.35))
            ya, yb = sorted((y_of(o), y_of(c)))
            img[max(0, ya):min(h, max(yb, ya + 1) + 1), max(0, x - bw):min(w, x + bw + 1)] = col
        for p, col, tf, dashed in lines or []:
            if p is None:
                continue
            y = y_of(p)
            if not 0 <= y < h:
                continue
            xa = max(pad_l, x_of(tf)) if tf else pad_l
            for x in range(xa, w - pad_r):
                if dashed and (x // 6) % 2:
                    continue
                img[max(0, y - 1):y + 1, x] = col
        for t, p, col in marks or []:
            if p is None:
                continue
            x, y = x_of(t), y_of(p)
            img[max(0, y - 5):min(h, y + 6), max(0, x - 5):min(w, x + 6)] = col
            img[max(0, y - 2):min(h, y + 3), max(0, x - 2):min(w, x + 3)] = BG
        return _png(img)
    except Exception:
        return None
