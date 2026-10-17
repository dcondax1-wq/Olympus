"""Contact sheet, 1:1 size strips and iPhone Home Screen simulations for app-icon concepts.

usage:
  python3 sheets.py contact OUT.png key:Label:path.png ...
  python3 sheets.py home OUT.png dark|light key:Label:path.png ...   (up to 8 concepts, placed once each)
  python3 sheets.py strip OUT.png 180,120,60 path.png ...           (every icon at each size, dark and light rows)
Real sizes: a Home Screen icon is 60 pt = 180 px at 3x; the sim is an iPhone 15 Pro screen (1179 x 2556 px).
"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

F_SEMI = '/usr/share/fonts/opentype/inter/Inter-SemiBold.otf'
F_MED = '/usr/share/fonts/opentype/inter/Inter-Medium.otf'
F_BOLD = '/usr/share/fonts/opentype/inter/Inter-Bold.otf'
RADIUS = 0.27   # corner radius as a fraction of the tile size (iOS-like rounded tile)


def font(path, px):
    return ImageFont.truetype(path, px)


def mask(size, r=RADIUS, ss=4):
    S = size * ss
    m = Image.new('L', (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * r), fill=255)
    return m.resize((size, size), Image.LANCZOS)


def tile(img, size, r=RADIUS):
    im = img.convert('RGB').resize((size, size), Image.LANCZOS)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask(size, r))
    return out


def shadow_text(base, xy, text, fnt, fill, anchor='mt', shadow=(0, 0, 0, 150), blur=3):
    lay = Image.new('RGBA', base.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((xy[0], xy[1] + 2), text, font=fnt, fill=shadow, anchor=anchor)
    lay = lay.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(lay)
    ImageDraw.Draw(base).text(xy, text, font=fnt, fill=fill, anchor=anchor)


def parse(items):
    out = []
    for it in items:
        k, label, path = it.split(':', 2)
        out.append((k, label, path))
    return out


def contact(out, items, big=480, title='Liquidity Engine: app icon concepts'):
    pad, small = 24, (180, 120, 60)
    cw = pad + big + pad + 180 + pad + 60 + pad + pad
    ch = big + 86
    cols = 2
    rows = (len(items) + cols - 1) // cols
    W, H = pad + cols * cw, 110 + rows * ch + pad
    sheet = Image.new('RGBA', (W, H), (14, 14, 19, 255))
    d = ImageDraw.Draw(sheet)
    d.text((pad + 8, 34), title, font=font(F_BOLD, 38), fill=(236, 236, 244))
    d.text((pad + 8, 80), 'ranked 1-8  ·  large  ·  180 / 120 / 60 px on dark  ·  60 px on light  (iOS-style 27% corner mask)', font=font(F_MED, 20), fill=(150, 150, 165))
    for i, (k, label, path) in enumerate(items):
        src = Image.open(path)
        cx, cy = pad + (i % cols) * cw, 110 + (i // cols) * ch
        d.rounded_rectangle([cx, cy, cx + cw - pad, cy + ch - 18], radius=18, fill=(22, 22, 29))
        t = tile(src, big)
        sheet.alpha_composite(t, (cx + pad, cy + pad))
        x = cx + pad + big + pad
        y = cy + pad
        for s in small:
            sheet.alpha_composite(tile(src, s), (x + (180 - s) // 2, y))
            y += s + 14
        lx = x + 180 + pad
        d.rounded_rectangle([lx - 12, cy + pad, lx + 60 + 12, cy + pad + 60 + 24], radius=12, fill=(236, 237, 243))
        sheet.alpha_composite(tile(src, 60), (lx, cy + pad + 12))
        d.text((cx + pad, cy + pad + big + 14), f'{i + 1}. {label}', font=font(F_SEMI, 26), fill=(236, 236, 244))
        d.text((cx + pad + big, cy + pad + big + 18), k, font=font(F_MED, 20), fill=(130, 130, 145), anchor='ra')
    sheet.convert('RGB').save(out)
    print(out, sheet.size)


PLACE = ['#34c759', '#0a84ff', '#ff9f0a', '#ff453a', '#ffd60a', '#8e8e93', '#64d2ff', '#5e5ce6', '#bf5af2', '#ff375f',
         '#30b0c7', '#ac8e68', '#32d74b', '#ff6b22', '#4a4a55', '#0071e3', '#e5e5ea', '#ff2d55', '#66d4cf', '#7d7aff']
NAMES = ['Mail', 'Calendar', 'Photos', 'Camera', 'Maps', 'Weather', 'Notes', 'Clock', 'Music', 'Wallet', 'Files', 'Health',
         'Podcasts', 'News', 'Books', 'Settings', 'Contacts', 'Fitness', 'Translate', 'Home']
DOCK = ['#34c759', '#0a84ff', '#30d158', '#ff375f']


def hexrgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def placeholder(size, colr):
    c = hexrgb(colr)
    top = tuple(min(255, int(v * 1.12 + 10)) for v in c)
    g = Image.new('RGB', (1, 2))
    g.putpixel((0, 0), top)
    g.putpixel((0, 1), c)
    g = g.resize((size, size), Image.BILINEAR)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(g, (0, 0), mask(size))
    return out


def wallpaper(W, H, mode):
    import numpy as np
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    x /= W
    y /= H

    def blob(cx, cy, rx, ry, col, a):
        return a * np.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2))[..., None] * np.array(col, np.float32)[None, None]
    if mode == 'dark':
        base = np.array([8, 10, 26], np.float32)[None, None] * (1 - 0.5 * y[..., None]) + np.array([3, 3, 8], np.float32) * y[..., None]
        img = base + blob(0.15, 0.2, 0.6, 0.35, (40, 60, 160), 0.55) + blob(0.9, 0.62, 0.55, 0.3, (90, 30, 120), 0.5) + blob(0.4, 0.95, 0.7, 0.25, (20, 70, 110), 0.45)
    else:
        base = np.array([236, 239, 250], np.float32)[None, None] * (1 - y[..., None]) + np.array([246, 240, 250], np.float32) * y[..., None]
        img = base - blob(0.15, 0.25, 0.55, 0.3, (40, 25, 0), 0.5) - blob(0.9, 0.65, 0.5, 0.3, (0, 35, 30), 0.55) - blob(0.45, 0.95, 0.7, 0.2, (35, 10, 0), 0.4)
    return Image.fromarray(np.clip(img, 0, 255).astype('uint8'), 'RGB').convert('RGBA')


def home(out, mode, items):
    W, H, icon = 1179, 2556, 180
    margin, gap, top, pitch = 81, 99, 222, 300
    scr = wallpaper(W, H, mode)
    d = ImageDraw.Draw(scr)
    ink = (255, 255, 255, 255) if mode == 'dark' else (20, 20, 26, 255)
    lab = (255, 255, 255, 255) if mode == 'dark' else (28, 28, 34, 255)
    # status bar
    d.text((150, 62), '9:41', font=font(F_SEMI, 50), fill=ink, anchor='mm')
    d.rounded_rectangle([W // 2 - 190, 34, W // 2 + 190, 140], radius=53, fill=(0, 0, 0, 255))   # dynamic island
    bx = W - 170
    d.rounded_rectangle([bx, 46, bx + 74, 80], radius=10, outline=ink, width=4)
    d.rounded_rectangle([bx + 7, 53, bx + 60, 73], radius=5, fill=ink)
    d.rounded_rectangle([bx + 78, 56, bx + 84, 70], radius=3, fill=ink)
    for i in range(4):
        h = 14 + i * 8
        d.rounded_rectangle([bx - 150 + i * 18, 80 - h, bx - 138 + i * 18, 80], radius=3, fill=ink)
    spots = [(0, 1), (0, 3), (1, 0), (1, 2), (2, 1), (2, 3), (3, 0), (3, 2)]
    concepts = {spots[i]: it for i, it in enumerate(items[:8])}
    fl = font(F_MED, 36)
    pi = 0
    for r in range(6):
        for c in range(4):
            x = margin + c * (icon + gap)
            y = top + r * pitch
            if (r, c) in concepts:
                k, label, path = concepts[(r, c)]
                t = tile(Image.open(path), icon)
                name = label
            else:
                t = placeholder(icon, PLACE[pi % len(PLACE)])
                name = NAMES[pi % len(NAMES)]
                pi += 1
            scr.alpha_composite(t, (x, y))
            if mode == 'dark':
                shadow_text(scr, (x + icon // 2, y + icon + 20), name, fl, lab)
            else:
                d.text((x + icon // 2, y + icon + 20), name, font=fl, fill=lab, anchor='mt')
    # page dots
    for i, a in enumerate((255, 110, 110)):
        cx = W // 2 - 30 + i * 30
        col = (255, 255, 255, a) if mode == 'dark' else (30, 30, 40, a)
        d.ellipse([cx - 8, 2120 - 8, cx + 8, 2120 + 8], fill=col)
    # dock
    dock = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dock)
    dcol = (255, 255, 255, 46) if mode == 'dark' else (255, 255, 255, 120)
    dd.rounded_rectangle([36, 2196, W - 36, 2496], radius=110, fill=dcol)
    scr.alpha_composite(dock)
    for c in range(4):
        x = margin + c * (icon + gap)
        scr.alpha_composite(placeholder(icon, DOCK[c]), (x, 2256))
    d.rounded_rectangle([W // 2 - 210, H - 34, W // 2 + 210, H - 20], radius=7, fill=ink)
    scr.convert('RGB').save(out)
    print(out, scr.size)


def strip(out, sizes, paths, gap=16):
    """Every icon at each size, 1:1 (no scaling of the sheet), on a dark row and a light row."""
    big = max(sizes)
    W = gap + len(paths) * (big + gap)
    H = sum((s + gap) * 2 for s in sizes) + gap
    im = Image.new('RGBA', (W, H), (12, 12, 18, 255))
    d = ImageDraw.Draw(im)
    srcs = [Image.open(p).convert('RGB') for p in paths]
    y = gap
    for s in sizes:
        for bg in ((12, 12, 18), (232, 234, 242)):
            d.rectangle([0, y - gap // 2, W, y + s + gap // 2], fill=bg)
            x = gap
            for src in srcs:
                im.alpha_composite(tile(src, s), (x + (big - s) // 2, y))
                x += big + gap
            y += s + gap
    im.convert('RGB').save(out)
    print(out, im.size)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'contact':
        contact(sys.argv[2], parse(sys.argv[3:]))
    elif cmd == 'home':
        home(sys.argv[2], sys.argv[3], parse(sys.argv[4:]))
    elif cmd == 'strip':
        strip(sys.argv[2], [int(v) for v in sys.argv[3].split(',')], sys.argv[4:])
