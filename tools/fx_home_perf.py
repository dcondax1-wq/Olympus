"""Gate + Doors effects check (night-effects, 2026-11-20).

Long tasks (> 50 ms) after load at 4x CPU slowdown, frames, sideways scroll, page errors, and screenshots / a short video.
    python tools/fx_home_perf.py --tag after [--shots DIR] [--video DIR] [--json FILE]
Serves tools/web_public on a free local port. Phone: 390 x 844, touch, dark (and light: html[data-oly-scheme=light]).
"""
import argparse, contextlib, functools, http.server, json, os, socketserver, sys, threading

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web_public')
PAGES = [('gate', 'gate/index.html'), ('doors', 'hub/doors.html#zeus')]

PROBE = r"""
window.__lt = []; window.__fr = [];
try { new PerformanceObserver(function (l) { l.getEntries().forEach(function (e) { window.__lt.push([Math.round(e.startTime), Math.round(e.duration)]); }); })
  .observe({ type: 'longtask', buffered: true }); } catch (e) {}
(function f(t) { window.__fr.push(t); if (window.__fr.length < 4000) requestAnimationFrame(f); })(performance.now());
"""


@contextlib.contextmanager
def serve():
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = functools.partial(Q, directory=ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    s = socketserver.ThreadingTCPServer(('127.0.0.1', 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    try:
        yield 'http://127.0.0.1:%d/' % s.server_address[1]
    finally:
        s.shutdown()


def measure(pw, base, page_id, path, light=False, shots=None, tag='', video=None):
    b = pw.chromium.launch()
    kw = dict(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, device_scale_factor=1, color_scheme='light' if light else 'dark')
    if video:
        kw['record_video_dir'] = video; kw['record_video_size'] = {'width': 390, 'height': 844}
    ctx = b.new_context(**kw)
    ctx.add_init_script(PROBE)
    if light:
        ctx.add_init_script("try{localStorage.setItem('olympus.theme','ivory')}catch(e){}")   # the owner's light look (themes.js), as on his phone
    p = ctx.new_page()
    errs = []
    p.on('pageerror', lambda e: errs.append(str(e)))
    cdp = ctx.new_cdp_session(p)
    cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
    p.goto(base + path, wait_until='load')
    load_ms = p.evaluate('performance.now()')
    p.wait_for_timeout(2500)
    if shots and not video:
        p.screenshot(path=os.path.join(shots, '%s-%s-390-%s.png' % (tag, page_id, 'light' if light else 'dark')))
    for y in (300, 700, 1100, 400, 0):
        p.mouse.wheel(0, y - p.evaluate('scrollY')); p.wait_for_timeout(450)
    try:   # one press on a door (press state + sheen)
        p.dispatch_event('.g-dr, .dr-door', 'pointerdown'); p.wait_for_timeout(200); p.dispatch_event('.g-dr, .dr-door', 'pointerup')
    except Exception:
        pass
    p.wait_for_timeout(1000)
    r = p.evaluate("""(lm) => { var lt = window.__lt.filter(x => x[0] > lm), fr = window.__fr, gaps = [];
      for (var i = 1; i < fr.length; i++) gaps.push(fr[i] - fr[i-1]);
      var slow = gaps.filter(g => g > 50).length;
      return { longtasks_after_load: lt.length, blocked_ms_after_load: lt.reduce((a, x) => a + x[1], 0), worst_ms: lt.reduce((a, x) => Math.max(a, x[1]), 0),
        all_longtasks: window.__lt.length, frames: fr.length, frames_over_50ms: slow,
        sideways: document.documentElement.scrollWidth > innerWidth + 1, fx: (document.documentElement.getAttribute('data-hfx') || '') + (window.OLYMPUS_HOMEFX ? ' ' + JSON.stringify(OLYMPUS_HOMEFX.state()) : '') }; }""", load_ms)
    r['load_ms'] = round(load_ms)
    r['errors'] = errs
    p.close(); ctx.close(); b.close()
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', default='now'); ap.add_argument('--shots'); ap.add_argument('--video'); ap.add_argument('--json')
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    out = {}
    with serve() as base, sync_playwright() as pw:
        for pid, path in PAGES:
            for light in (False, True):
                key = '%s-%s' % (pid, 'light' if light else 'dark')
                out[key] = measure(pw, base, pid, path, light, a.shots, a.tag)
                print(key, json.dumps(out[key]))
        if a.video:
            measure(pw, base, 'gate', PAGES[0][1], video=a.video)
    if a.json:
        with open(a.json, 'w') as f:
            json.dump(out, f, indent=1)
    bad = [k for k, v in out.items() if v['errors'] or v['sideways']]
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
