"""A small QR code maker (ISO/IEC 18004, byte mode), pure Python, no dependencies.

Used by make_review.py to print the review card QR as a vector SVG (crisp at any print size, no web service involved).

    from agency.upsells import qr
    code = qr.make("https://example.com/review/", ecl="Q")     # Q = 25% of the code can be scuffed and it still scans
    code.version, code.size, code.mask                         # 4, 33, <0..7>
    code.svg(title="Review us")                                # '<svg ...>' (4-module quiet zone, one path)

Checked against the reference library segno (every version 1-40 x every level, same mask = same modules) and read back with
zxing-cpp during the build (2026-11-14); the repo test decodes the SVG with its own reader (tests/test_agency_upsells.py).
"""
from __future__ import annotations

import collections

# error correction level -> (table row, the 2 format bits)
LEVELS = {"L": (0, 1), "M": (1, 0), "Q": (2, 3), "H": (3, 2)}

# per version 1..40 (index 0 unused): error correction codewords per block, and the number of blocks
ECC_PER_BLOCK = (
    (-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),
    (-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    (-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
)
NUM_BLOCKS = (
    (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25),
    (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49),
    (-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),
    (-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81),
)
MASKS = (
    lambda x, y: (x + y) % 2,
    lambda x, y: y % 2,
    lambda x, y: x % 3,
    lambda x, y: (x + y) % 3,
    lambda x, y: (x // 3 + y // 2) % 2,
    lambda x, y: x * y % 2 + x * y % 3,
    lambda x, y: (x * y % 2 + x * y % 3) % 2,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2,
)


def raw_modules(ver: int) -> int:
    """data + error correction modules of a version (everything but the function patterns)"""
    n = (16 * ver + 128) * ver + 64
    if ver >= 2:
        k = ver // 7 + 2
        n -= (25 * k - 10) * k - 55
        if ver >= 7:
            n -= 36
    return n


def data_codewords(ver: int, ecl: str) -> int:
    row = LEVELS[ecl][0]
    return raw_modules(ver) // 8 - ECC_PER_BLOCK[row][ver] * NUM_BLOCKS[row][ver]


def alignment_positions(ver: int) -> list:
    if ver == 1:
        return []
    k = ver // 7 + 2
    step = (ver * 8 + k * 3 + 5) // (k * 4 - 4) * 2
    size = ver * 4 + 17
    return [6] + [size - 7 - i * step for i in range(k - 1)][::-1]


def _gf_mul(x: int, y: int) -> int:
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> list:
    out = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            out[j] = _gf_mul(out[j], root)
            if j + 1 < degree:
                out[j] ^= out[j + 1]
        root = _gf_mul(root, 2)
    return out


def _rs_remainder(data: list, divisor: list) -> list:
    out = [0] * len(divisor)
    for b in data:
        f = b ^ out.pop(0)
        out.append(0)
        for i, c in enumerate(divisor):
            out[i] ^= _gf_mul(c, f)
    return out


class QR:
    def __init__(self, text: str, ver: int, ecl: str, codewords: list, mask: int | None):
        self.text, self.version, self.ecl = text, ver, ecl
        self.size = ver * 4 + 17
        n = self.size
        self.modules = [[False] * n for _ in range(n)]
        self._fn = [[False] * n for _ in range(n)]
        self._functions()
        self._place(self._interleave(codewords))
        if mask is None:
            best = None
            for m in range(8):
                self._mask(m)
                self._format(m)
                p = self.penalty()
                if best is None or p < best[0]:
                    best = (p, m)
                self._mask(m)                       # XOR again = undo
            mask = best[1]
        self._mask(mask)
        self._format(mask)
        self.mask = mask
        del self._fn

    # ---- function patterns
    def _set(self, x, y, dark):
        self.modules[y][x] = bool(dark)
        self._fn[y][x] = True

    def _functions(self):
        n = self.size
        for i in range(n):
            self._set(6, i, i % 2 == 0)
            self._set(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < n and 0 <= y < n:
                        self._set(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        pos = alignment_positions(self.version)
        last = len(pos) - 1
        for i, a in enumerate(pos):
            for j, b in enumerate(pos):
                if (i, j) in ((0, 0), (0, last), (last, 0)):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self._set(a + dx, b + dy, max(abs(dx), abs(dy)) != 1)
        self._format(0)
        if self.version >= 7:
            rem = self.version
            for _ in range(12):
                rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
            bits = self.version << 12 | rem
            for i in range(18):
                bit = (bits >> i) & 1
                a, b = n - 11 + i % 3, i // 3
                self._set(a, b, bit)
                self._set(b, a, bit)

    def _format(self, mask):
        n = self.size
        data = LEVELS[self.ecl][1] << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        bit = lambda i: (bits >> i) & 1  # noqa: E731
        for i in range(6):
            self._set(8, i, bit(i))
        self._set(8, 7, bit(6))
        self._set(8, 8, bit(7))
        self._set(7, 8, bit(8))
        for i in range(9, 15):
            self._set(14 - i, 8, bit(i))
        for i in range(8):
            self._set(n - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self._set(8, n - 15 + i, bit(i))
        self._set(8, n - 8, True)

    # ---- data
    def _interleave(self, data):
        row = LEVELS[self.ecl][0]
        nblocks, ecclen = NUM_BLOCKS[row][self.version], ECC_PER_BLOCK[row][self.version]
        raw = raw_modules(self.version) // 8
        nshort, shortlen = nblocks - raw % nblocks, raw // nblocks
        div = _rs_divisor(ecclen)
        blocks, k = [], 0
        for i in range(nblocks):
            dat = data[k:k + shortlen - ecclen + (0 if i < nshort else 1)]
            k += len(dat)
            ecc = _rs_remainder(dat, div)
            if i < nshort:
                dat = dat + [0]
            blocks.append(dat + ecc)
        out = []
        for i in range(len(blocks[0])):
            for j, blk in enumerate(blocks):
                if i != shortlen - ecclen or j >= nshort:
                    out.append(blk[i])
        return out

    def _place(self, data):
        n, i, total = self.size, 0, len(data) * 8
        right = n - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(n):
                for j in range(2):
                    x = right - j
                    up = ((right + 1) & 2) == 0
                    y = n - 1 - vert if up else vert
                    if not self._fn[y][x] and i < total:
                        self.modules[y][x] = bool((data[i >> 3] >> (7 - (i & 7))) & 1)
                        i += 1
            right -= 2

    def _mask(self, m):
        f = MASKS[m]
        for y in range(self.size):
            row, fn = self.modules[y], self._fn[y]
            for x in range(self.size):
                if not fn[x] and f(x, y) == 0:
                    row[x] = not row[x]

    # ---- mask choice (the standard's four penalty rules)
    def penalty(self) -> int:
        n, m, score = self.size, self.modules, 0
        lines = [m[y] for y in range(n)] + [[m[y][x] for y in range(n)] for x in range(n)]
        for line in lines:
            color, run, hist = False, 0, collections.deque([0] * 7, 7)
            for cell in line:
                if cell == color:
                    run += 1
                    if run == 5:
                        score += 3
                    elif run > 5:
                        score += 1
                else:
                    self._hist_add(run, hist)
                    if not color:
                        score += self._finder_like(hist) * 40
                    color, run = cell, 1
            if color:
                self._hist_add(run, hist)
                run = 0
            self._hist_add(run + n, hist)
            score += self._finder_like(hist) * 40
        for y in range(n - 1):
            for x in range(n - 1):
                if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    score += 3
        dark = sum(c for r in m for c in r)
        total = n * n
        score += ((abs(dark * 20 - total * 10) + total - 1) // total - 1) * 10
        return score

    def _hist_add(self, run, hist):
        if hist[0] == 0:
            run += self.size
        hist.appendleft(run)

    @staticmethod
    def _finder_like(h):
        n = h[1]
        core = n > 0 and h[2] == h[4] == h[5] == n and h[3] == n * 3
        return (1 if core and h[0] >= n * 4 and h[6] >= n else 0) + (1 if core and h[6] >= n * 4 and h[0] >= n else 0)

    # ---- output
    def rows(self) -> list:
        return ["".join("1" if c else "0" for c in r) for r in self.modules]

    def svg(self, border: int = 4, dark: str = "#000000", light: str = "#ffffff", title: str = "", css_class: str = "") -> str:
        """one <path> of horizontal runs; viewBox in modules, so the caller sets the printed size with CSS"""
        n, dim = self.size, self.size + 2 * border
        parts = []
        for y, row in enumerate(self.modules):
            x = 0
            while x < n:
                if row[x]:
                    x0 = x
                    while x < n and row[x]:
                        x += 1
                    parts.append(f"M{x0 + border} {y + border}h{x - x0}v1h-{x - x0}z")
                else:
                    x += 1
        label = _esc(title or self.text)
        cls = f' class="{_esc(css_class)}"' if css_class else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}"{cls} shape-rendering="crispEdges" role="img" aria-label="{label}">'
                f'<title>{label}</title><rect width="{dim}" height="{dim}" fill="{light}"/><path fill="{dark}" d="{"".join(parts)}"/></svg>')


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def make(text: str, ecl: str = "Q", version: int | None = None, mask: int | None = None) -> QR:
    """byte mode; ASCII only (a URL: percent-encode anything else first) so every phone camera reads it the same way"""
    if ecl not in LEVELS:
        raise ValueError(f"ecl must be one of L M Q H, not {ecl!r}")
    if any(ord(c) > 126 or ord(c) < 32 for c in text):
        raise ValueError("QR text must be plain printable ASCII (percent-encode the rest)")
    data = text.encode("ascii")
    versions = [version] if version else range(1, 41)
    for ver in versions:
        cap = data_codewords(ver, ecl) * 8
        used = 4 + (8 if ver < 10 else 16) + len(data) * 8
        if used <= cap:
            break
    else:
        raise ValueError(f"text too long for a QR code at level {ecl} ({len(data)} bytes)")
    bits = []

    def put(val, n):
        bits.extend((val >> i) & 1 for i in range(n - 1, -1, -1))

    put(0b0100, 4)
    put(len(data), 8 if ver < 10 else 16)
    for b in data:
        put(b, 8)
    put(0, min(4, cap - len(bits)))
    put(0, (-len(bits)) % 8)
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(words) < cap // 8:
        words.append(pad)
        pad ^= 0xEC ^ 0x11
    return QR(text, ver, ecl, words, mask)


if __name__ == "__main__":
    import sys
    code = make(sys.argv[1] if len(sys.argv) > 1 else "https://example.com/review/")
    print(f"version {code.version}, level {code.ecl}, mask {code.mask}, {code.size}x{code.size} modules")
    for r in code.rows():
        print(r.replace("1", "##").replace("0", "  "))
