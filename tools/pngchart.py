"""Tiny stdlib PNG candle chart (the PC has no matplotlib): one trade's 5m candles + entry / stop / target / exit, OLYMPUS NIGHT
colours (black, violet grid, gold entry, mint target, red stop). Used by tools/journal_build.py. No dependency beyond zlib.

    png = candle_png(bars, entry=..., stop=..., target=..., exit_px=..., t_in=..., t_out=..., side=1, title="...")
bars = [(t, o, h, l, c), ...] (unix s, ascending). Returns PNG bytes.
"""
from __future__ import annotations

import struct
import zlib

BG = (0, 0, 0)
GRID = (62, 37, 94)          # #3e255e
UP = (119, 219, 137)         # mint #77db89
DN = (230, 84, 84)
GOLD = (241, 193, 75)        # #f1c14b
VIOLET = (157, 89, 238)      # #9d59ee
WHITE = (230, 226, 240)

# 5x7 digit / letter glyphs for the price labels and the title (only what we print)
_G = {
    "0": "01110100011001110101110011000101110", "1": "00100011000010000100001000010001110", "2": "01110100010000100010001000100011111",
    "3": "11111000100010000010000011000101110", "4": "00010001100101010010111110001000010", "5": "11111100001111000001000011000101110",
    "6": "00110010001000011110100011000101110", "7": "11111000010001000100010000100001000", "8": "01110100011000101110100011000101110",
    "9": "01110100011000101111000010001001100", ".": "00000000000000000000000000110001100", "-": "00000000000111000000000000000000000",
    "+": "00000001000010011111001000010000000", ":": "00000011000110000000011000110000000", " ": "0" * 35, "R": "11110100011000111110101001001010001",
    "L": "10000100001000010000100001000011111", "S": "01111100001000001110000010000111110", "E": "11111100001000011110100001000011111",
    "T": "11111001000010000100001000010000100", "O": "01110100011000110001100011000101110", "N": "10001100011100110101100111000110001",
    "G": "01110100011000010111100011000101111", "H": "10001100011000111111100011000110001", "A": "01110100011000111111100011000110001",
    "X": "10001100010101000100010101000110001", "P": "11110100011000111110100001000010000", "I": "01110001000010000100001000010001110",
    "$": "00100011111010001110001011111000100", "/": "00001000100001000100001000100000000", "B": "11110100011000111110100011000111110",
    "C": "01110100011000010000100001000101110", "D": "11100100101000110001100011001011100", "M": "10001110111010110001100011000110001",
    "U": "10001100011000110001100011000101110", "V": "10001100011000110001100010101000100", "W": "10001100011000110101101011101110001",
    "K": "10001100101010011000101001001010001", "F": "11111100001000011110100001000010000", "Y": "10001100010101000100001000010000100",
    "Z": "11111000010001000100010001000011111", "J": "00111000100001000010000101001001100", "Q": "01110100011000110001101011001001101",
}


class Canvas:
    def __init__(self, w: int, h: int, bg=BG):
        self.w, self.h = w, h
        self.px = bytearray(bytes(bg) * (w * h))

    def put(self, x: int, y: int, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = 3 * (y * self.w + x)
            self.px[i:i + 3] = bytes(c)

    def rect(self, x0, y0, x1, y1, c):
        x0, x1 = sorted((int(x0), int(x1)))
        y0, y1 = sorted((int(y0), int(y1)))
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.w - 1, x1), min(self.h - 1, y1)
        row = bytes(c) * (x1 - x0 + 1)
        for y in range(y0, y1 + 1):
            i = 3 * (y * self.w + x0)
            self.px[i:i + len(row)] = row

    def hline(self, y, c, x0=0, x1=None, dash=0):
        x1 = self.w - 1 if x1 is None else x1
        for x in range(int(x0), int(x1) + 1):
            if not dash or (x // dash) % 2 == 0:
                self.put(x, int(y), c)

    def vline(self, x, c, y0=0, y1=None, dash=0):
        y1 = self.h - 1 if y1 is None else y1
        for y in range(int(y0), int(y1) + 1):
            if not dash or (y // dash) % 2 == 0:
                self.put(int(x), y, c)

    def text(self, x, y, s, c, scale=1):
        for ch in str(s).upper():
            g = _G.get(ch, _G[" "])
            for k, bit in enumerate(g):
                if bit == "1":
                    gx, gy = k % 5, k // 5
                    self.rect(x + gx * scale, y + gy * scale, x + gx * scale + scale - 1, y + gy * scale + scale - 1, c)
            x += 6 * scale

    def png(self) -> bytes:
        raw = b"".join(b"\x00" + bytes(self.px[3 * y * self.w:3 * (y + 1) * self.w]) for y in range(self.h))

        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def candle_png(bars, entry=None, stop=None, target=None, exit_px=None, t_in=None, t_out=None, side=1, title="",
               w: int = 720, h: int = 360) -> bytes:
    cv = Canvas(w, h)
    L, R, T, B = 8, 70, 18, h - 10
    lv = [p for p in (entry, stop, target, exit_px) if p is not None]
    if not bars:
        cv.text(10, h // 2, "NO BARS", WHITE, 2)
        return cv.png()
    hi = max(max(b[2] for b in bars), *(lv or [-1e18]))
    lo = min(min(b[3] for b in bars), *(lv or [1e18]))
    pad = (hi - lo) * 0.06 or 1.0
    hi, lo = hi + pad, lo - pad

    def Y(p):
        return T + (hi - p) / (hi - lo) * (B - T)
    n = len(bars)
    step = (w - L - R) / max(1, n)
    for k in range(1, 5):                                      # grid + price labels
        p = lo + (hi - lo) * k / 5
        cv.hline(Y(p), GRID, L, w - R, dash=3)
        cv.text(w - R + 4, int(Y(p)) - 3, f"{p:.0f}", GRID)

    def X(t):
        k = 0
        while k < n - 1 and bars[k + 1][0] <= t:
            k += 1
        return L + (k + 0.5) * step
    if t_in is not None:
        cv.vline(X(t_in), VIOLET, T, B, dash=2)
    if t_out is not None:
        cv.vline(X(t_out), VIOLET, T, B, dash=2)
    for k, (t, o, hh, ll, c) in enumerate(bars):
        x = L + (k + 0.5) * step
        col = UP if c >= o else DN
        cv.vline(x, col, Y(hh), Y(ll))
        bw = max(1, int(step * 0.35))
        cv.rect(x - bw, Y(max(o, c)), x + bw, Y(min(o, c)), col)
    for p, col, lab in ((stop, DN, "STOP"), (target, UP, "TGT"), (entry, GOLD, "ENTRY")):
        if p is not None:
            cv.hline(Y(p), col, L, w - R)
            cv.text(w - R + 4, int(Y(p)) - 3, f"{p:.2f}"[:8], col)
    if exit_px is not None and t_out is not None:
        x, y = X(t_out), Y(exit_px)
        cv.rect(x - 3, y - 3, x + 3, y + 3, WHITE)
    cv.text(L, 4, title[:100], WHITE)
    return cv.png()
