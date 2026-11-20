"""Screenshots (390 x 844 at 2x, dark + the Ivory light look) and a 6 s video of the living home with live bot numbers (test fixture).
    python tools/fx_home_shots.py DIR [--tag after]"""
import os, sys, glob, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import test_gate_page as GP  # noqa: E402
from tools import fx_home_perf as F  # noqa: E402


def main():
    out = sys.argv[1]; tag = sys.argv[sys.argv.index('--tag') + 1] if '--tag' in sys.argv else 'after'
    os.makedirs(out, exist_ok=True)
    from playwright.sync_api import sync_playwright
    with F.serve() as base, sync_playwright() as pw:
        b = pw.chromium.launch()
        for light in (False, True):
            for vid in ((False, True) if not light else (False,)):
                kw = dict(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, device_scale_factor=1 if vid else 2, color_scheme='light' if light else 'dark')
                if vid:
                    kw.update(record_video_dir=out, record_video_size={'width': 390, 'height': 844})
                ctx = b.new_context(**kw)
                if light:
                    ctx.add_init_script("try{localStorage.setItem('olympus.theme','ivory')}catch(e){}")
                ctx.route('**/home.json*', lambda r: r.fulfill(status=200, content_type='application/json', body=GP.home_json(300)))
                p = ctx.new_page()
                sch = 'light' if light else 'dark'
                for pid, path in (('gate', 'gate/index.html?hfx=1&now=' + GP.NOW), ('doors', 'hub/doors.html#zeus')):
                    p.goto(base + path)
                    if vid:
                        p.wait_for_timeout(2600)
                        for y in (250, 520, 250, 0):
                            p.mouse.wheel(0, y - p.evaluate('scrollY')); p.wait_for_timeout(350)
                        el = p.locator('.g-dr, .dr-door').first; bx = el.bounding_box()
                        p.mouse.move(bx['x'] + 40, bx['y'] + 30); p.mouse.down(); p.wait_for_timeout(260); p.mouse.up(); p.wait_for_timeout(500)
                        break
                    p.wait_for_timeout(2600)
                    p.screenshot(path=os.path.join(out, '%s-%s-live-390-%s.png' % (tag, pid, sch)))
                    if pid == 'gate':
                        p.evaluate('window.scrollTo(0, 420)'); p.wait_for_timeout(400)
                        p.screenshot(path=os.path.join(out, '%s-gate-live-390-%s-now.png' % (tag, sch)))
                ctx.close()
                if vid:
                    v = sorted(glob.glob(os.path.join(out, '*.webm')), key=os.path.getmtime)[-1]
                    shutil.move(v, os.path.join(out, '%s-gate-6s.webm' % tag))
        b.close()


if __name__ == '__main__':
    main()
