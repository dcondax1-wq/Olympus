"""Liquidity Engine app icon v2: render every concept master, then the previews, sheets and final asset sets.

usage (from this folder, after `npm install` here; needs Playwright + Chromium, numpy, Pillow):
  python3 build.py all              masters + previews + sheets + final assets (about 5-10 min on 4 cores)
  python3 build.py masters [names]  re-render masters into out/ (names: see MASTERS)
  python3 build.py sheets           previews/*.png, contact_sheet.png, homescreen_dark.png, homescreen_light.png
  python3 build.py assets           final/<concept>/ for the two finalists

Three.js scenes are served from this folder on 127.0.0.1:8799 (started and stopped here).
"""
import base64
import os
import shutil
import subprocess
import sys
import time
import urllib.request

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # research/design/icon_v2
OUT = os.path.join(HERE, 'out')
sys.path.insert(0, os.path.join(HERE, 'py'))
import sheets  # noqa: E402

# name -> (kind, source, render px, extra query for scenes)
MASTERS = {
    'chrome_drop':      ('scene', 'chrome_drop', 1024, 'ss=4'),
    'chrome_drop_mask': ('scene', 'chrome_drop', 1024, 'ss=4&zoom=1.2'),   # camera pulled back: art inside the 80% circle
    'sweep':            ('svg', 'svg/sweep.svg', 2048, ''),
    'sweep_mask':       ('svg', 'out/sweep_mask.svg', 2048, ''),          # same art scaled 0.8 about the centre
    'reactor':          ('py', 'py/reactor.py', 2048, ''),
    'eclipse':          ('py', 'py/eclipse.py', 2048, ''),
    'prism':            ('svg', 'svg/prism.svg', 1024, ''),
    'hex_engine':       ('svg', 'svg/hex_engine.svg', 1024, ''),
    'glass_tile':       ('scene', 'glass_tile', 1024, ''),
    'ribbon':           ('scene', 'ribbon', 1024, ''),
}
# ranked order (contact sheet, Home Screen sims, previews)
CONCEPTS = [('chrome_drop', 'Chrome Drop'), ('sweep', 'Sweep'), ('reactor', 'Reactor'), ('eclipse', 'Eclipse'),
            ('hex_engine', 'Hex Engine'), ('prism', 'Prism'), ('glass_tile', 'Glass Tile'), ('ribbon', 'Ribbon')]
FINALISTS = ['chrome_drop', 'sweep']
VECTOR = {'sweep': 'svg/sweep.svg'}


def master_path(name):
    return os.path.join(OUT, f'{name}_{MASTERS[name][2]}.png')


def node_env():
    env = dict(os.environ)
    root = subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True).stdout.strip()
    env['NODE_PATH'] = root
    return env


def make_mask_svg():
    s = open(os.path.join(HERE, 'svg/sweep.svg')).read()
    s = s.replace('<g id="art">', '<g id="art" transform="translate(512 512) scale(0.8) translate(-512 -512)">', 1)
    open(os.path.join(OUT, 'sweep_mask.svg'), 'w').write(s)


def render_masters(names):
    os.makedirs(OUT, exist_ok=True)
    make_mask_svg()
    env = node_env()
    scenes = [n for n in names if MASTERS[n][0] == 'scene']
    server = None
    try:
        if scenes:
            if not os.path.isdir(os.path.join(HERE, 'node_modules', 'three')):
                sys.exit('three.js missing: run `npm install` in ' + HERE)
            server = subprocess.Popen([sys.executable, '-m', 'http.server', '8799', '--bind', '127.0.0.1'], cwd=HERE,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(50):
                try:
                    urllib.request.urlopen('http://127.0.0.1:8799/render.html', timeout=1)
                    break
                except OSError:
                    time.sleep(0.2)
        for n in names:
            kind, src, px, extra = MASTERS[n]
            t0 = time.time()
            if kind == 'scene':
                spec = src + ('?' + extra if extra else '')
                subprocess.run(['node', 'shot.js', str(px), spec], cwd=HERE, env={**env, 'NAME': n}, check=True)
            elif kind == 'svg':
                subprocess.run(['node', 'svg2png.js', str(px), OUT, src], cwd=HERE, env=env, check=True)
                base = os.path.splitext(os.path.basename(src))[0]
                if base != n:
                    os.replace(os.path.join(OUT, f'{base}_{px}.png'), master_path(n))
            else:
                subprocess.run([sys.executable, src, master_path(n), str(px), str(px)], cwd=HERE, check=True)
            print(f'{n}: {time.time() - t0:.0f}s')
    finally:
        if server:
            server.terminate()
            server.wait()


def load(name, size=None):
    im = Image.open(master_path(name)).convert('RGB')
    if size and im.size[0] != size:
        im = im.resize((size, size), Image.LANCZOS)
    return im


def small(im, size):
    """LANCZOS downscale; a light unsharp mask at <= 192 px keeps the neon rims crisp at Home Screen size."""
    out = im.resize((size, size), Image.LANCZOS)
    if size <= 192:
        out = out.filter(ImageFilter.UnsharpMask(radius=0.8 if size > 120 else 0.6, percent=45, threshold=2))
    return out


def build_sheets():
    os.makedirs(os.path.join(ROOT, 'previews'), exist_ok=True)
    items = []
    for k, label in CONCEPTS:
        p = os.path.join(ROOT, 'previews', f'{k}_512.png')
        load(k, 1024).resize((512, 512), Image.LANCZOS).save(p, optimize=True)
        items.append((k, label, master_path(k)))
    sheets.contact(os.path.join(ROOT, 'contact_sheet.png'), items, title='Liquidity Engine: app icon concepts v2, ranked')
    sheets.home(os.path.join(ROOT, 'homescreen_dark.png'), 'dark', items)
    sheets.home(os.path.join(ROOT, 'homescreen_light.png'), 'light', items)
    finals = [(k, lbl, master_path(k)) for k, lbl in CONCEPTS if k in FINALISTS]
    sheets.strip(os.path.join(ROOT, 'final', 'small_sizes_check.png'), (180, 120, 60, 40), [p for _, _, p in finals])


def build_assets():
    for k in FINALISTS:
        d = os.path.join(ROOT, 'final', k)
        os.makedirs(d, exist_ok=True)
        big = load(k)
        mask = load(k + '_mask')
        big.resize((1024, 1024), Image.LANCZOS).save(os.path.join(d, 'icon-1024.png'), optimize=True)
        big.resize((512, 512), Image.LANCZOS).save(os.path.join(d, 'icon-512.png'), optimize=True)
        small(big, 192).save(os.path.join(d, 'icon-192.png'), optimize=True)
        small(big, 180).save(os.path.join(d, 'apple-touch-icon.png'), optimize=True)
        mask.resize((512, 512), Image.LANCZOS).save(os.path.join(d, 'icon-maskable-512.png'), optimize=True)
        if k in VECTOR:
            shutil.copyfile(os.path.join(HERE, VECTOR[k]), os.path.join(d, 'icon.svg'))
        else:
            b64 = base64.b64encode(open(os.path.join(d, 'icon-512.png'), 'rb').read()).decode()
            open(os.path.join(d, 'icon.svg'), 'w').write(
                '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 512 512" width="512" height="512">'
                f'<!-- Liquidity Engine app icon "{k}" (3D render, research/design/icon_v2/src) -->'
                f'<image width="512" height="512" href="data:image/png;base64,{b64}" xlink:href="data:image/png;base64,{b64}"/></svg>\n')
        print(k, sorted(os.listdir(d)))


if __name__ == '__main__':
    step = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if step in ('all', 'masters'):
        render_masters(sys.argv[2:] if step == 'masters' and len(sys.argv) > 2 else list(MASTERS))
    if step in ('all', 'sheets'):
        build_sheets()
    if step in ('all', 'assets'):
        build_assets()
