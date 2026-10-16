"""Render the PWA icons (PNG) from the same design as icon.svg, using Pillow. Run once: python make_icons.py

Design (512 design units, see icon.svg): a hexagonal aperture, a luminous "sweep" along its lower edges,
a broken liquidity level line, and a candle whose lower wick pierces the level and takes the liquidity below it.
"""
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))

BG0, BG1 = (13, 22, 38), (5, 8, 15)         # background gradient
BLUE, CYAN, TEAL = (59, 157, 255), (34, 211, 238), (45, 212, 164)

HEX = [(256, 60), (425.7, 158), (425.7, 354), (256, 452), (86.3, 354), (86.3, 158)]
SWEEP = [(86.3, 158), (86.3, 354), (256, 452), (425.7, 354)]


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def render(size, maskable=False):
    S = 1024                                   # supersample, then LANCZOS down
    k = 0.78 if maskable else 1.0              # maskable: keep the mark inside the 80% safe zone
    sc = S / 512.0
    cx = cy = S / 2.0

    def P(x, y):
        return (cx + (x * sc - cx) * k, cy + (y * sc - cy) * k)

    def W(w):
        return max(1, int(round(w * sc * k)))

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # background: diagonal gradient, rounded unless maskable (full bleed)
    grad = Image.new("RGBA", (S, S))
    gpx = grad.load()
    for y in range(S):
        for x in range(0, S, 4):
            c = lerp(BG0, BG1, (x + y) / (2.0 * S))
            for dx in range(4):
                if x + dx < S:
                    gpx[x + dx, y] = c + (255,)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=0 if maskable else 224, fill=255)
    img.paste(grad, (0, 0), mask)
    # soft accent pool in the top-left corner
    pool = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(pool).ellipse([-S * 0.35, -S * 0.45, S * 0.75, S * 0.55], fill=BLUE + (70,))
    pool = pool.filter(ImageFilter.GaussianBlur(160))
    img.alpha_composite(Image.composite(pool, Image.new("RGBA", (S, S), (0, 0, 0, 0)), mask))

    d = ImageDraw.Draw(img)
    hexpts = [P(*p) for p in HEX]
    # faint full aperture
    ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(ring).line(hexpts + [hexpts[0], hexpts[1]], fill=BLUE + (82,), width=W(22), joint="curve")
    img.alpha_composite(ring)
    # the sweep: glow pass then a cyan->blue gradient stroke along the lower three edges
    sweep = [P(*p) for p in SWEEP]
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).line(sweep, fill=CYAN + (170,), width=W(30), joint="curve")
    glow = glow.filter(ImageFilter.GaussianBlur(26))
    img.alpha_composite(glow)
    segs = []
    for i in range(len(sweep) - 1):
        (x0, y0), (x1, y1) = sweep[i], sweep[i + 1]
        n = 18
        for j in range(n):
            segs.append(((x0 + (x1 - x0) * j / n, y0 + (y1 - y0) * j / n), (x0 + (x1 - x0) * (j + 1) / n, y0 + (y1 - y0) * (j + 1) / n)))
    # opaque gradient stroke on its own layer, faded in through an L mask (no seams between the sub-segments)
    total = len(segs)
    sw = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    swd = ImageDraw.Draw(sw)
    fade = Image.new("L", (S, S), 0)
    fd = ImageDraw.Draw(fade)
    r = W(22) / 2.0
    for i, (a, b) in enumerate(segs):
        t = i / float(total - 1)
        col = lerp(CYAN, BLUE, max(0.0, (t - 0.45) / 0.55)) if t > 0.45 else CYAN
        alpha = int(40 + 215 * min(1.0, t / 0.45)) if t < 0.45 else 255
        swd.line([a, b], fill=col + (255,), width=W(22))
        swd.ellipse([b[0] - r, b[1] - r, b[0] + r, b[1] + r], fill=col + (255,))
        fd.line([a, b], fill=alpha, width=W(22))
        fd.ellipse([b[0] - r, b[1] - r, b[0] + r, b[1] + r], fill=alpha)
    sw.putalpha(ImageChops.multiply(sw.getchannel("A"), fade))
    img.alpha_composite(sw)
    # liquidity level, broken where the wick pierces it
    for (xa, xb) in ((128, 232), (280, 384)):
        a, b = P(xa, 312), P(xb, 312)
        d.line([a, b], fill=BLUE + (150,), width=W(14))
        r = W(14) / 2.0
        for (x, y) in (a, b):
            d.ellipse([x - r, y - r, x + r, y + r], fill=BLUE + (150,))
    # wicks
    for (ya, yb) in ((122, 158), (300, 392)):
        a, b = P(256, ya), P(256, yb)
        d.line([a, b], fill=CYAN + (255,), width=W(16))
        r = W(16) / 2.0
        for (x, y) in (a, b):
            d.ellipse([x - r, y - r, x + r, y + r], fill=CYAN + (255,))
    # candle body with a vertical cyan->blue gradient
    (bx0, by0), (bx1, by1) = P(230, 158), P(282, 300)
    body = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bpx = body.load()
    for y in range(int(by0), int(by1) + 1):
        c = lerp(CYAN, BLUE, (y - by0) / max(1.0, by1 - by0))
        for x in range(int(bx0), int(bx1) + 1):
            bpx[x, y] = c + (255,)
    bmask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(bmask).rounded_rectangle([bx0, by0, bx1, by1], radius=W(11), fill=255)
    img.paste(body, (0, 0), bmask)
    # glowing tip where the wick took the liquidity
    tx, ty = P(256, 392)
    tr = W(16)
    tip = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(tip).ellipse([tx - tr * 1.6, ty - tr * 1.6, tx + tr * 1.6, ty + tr * 1.6], fill=TEAL + (200,))
    tip = tip.filter(ImageFilter.GaussianBlur(22))
    img.alpha_composite(tip)
    d.ellipse([tx - tr, ty - tr, tx + tr, ty + tr], fill=TEAL + (255,))
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    render(192).save(os.path.join(HERE, "icon-192.png"))
    render(512).save(os.path.join(HERE, "icon-512.png"))
    render(180).save(os.path.join(HERE, "apple-touch-icon.png"))
    render(512, maskable=True).save(os.path.join(HERE, "icon-maskable-512.png"))
    print("icons written")
