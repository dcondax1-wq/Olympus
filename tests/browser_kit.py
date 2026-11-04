"""Shared browser helper for the Playwright suites (2026-11-04, job 23: on the shared slow machine browser suites took hours or timed out).

    from tests import browser_kit as BK           (or: import browser_kit as BK when run from tests/)
    br = BK.launch(pw)                            # instead of pw.chromium.launch(...): same asserts, only launch and waits change
    br = BK.launch(pw, args=["--use-gl=angle"])   # a suite's own extra flags are kept

What it does (nothing here changes what a suite asserts):
  - the pre-installed Chromium (/opt/pw-browsers/chromium-*/chrome-linux/chrome), --no-sandbox and the SwiftShader flags;
  - ONE browser per Playwright instance: a second launch(pw) in the same `with sync_playwright()` returns the live one and its
    close() is a no-op (the real close is at exit), so a suite that opens a browser per section does not pay a start each time;
    a crashed or closed browser is launched again;
  - timeouts scaled by the measured load: multiplier = clamp(load1 / cpus / 1.5, 1, 6). The default timeout of every context and page,
    and every explicit timeout= passed to goto / wait_for_function / wait_for_selector / click / fill / text_content ..., is multiplied;
  - one automatic retry of a flaky wait (a Playwright TimeoutError on those calls, Page / Frame / Locator, and a failed expect(...).to_*) when the machine is loaded (multiplier >= 2);
    BK_RETRY=0 turns it off;
  - BK.limit(seconds) / BK.limit_ms(ms): a wall-clock assert limit that is exactly as written on a quiet machine and x the multiplier
    under load (and says so in the output)
  - BK_FAST=1 (opt-in; run_area.py --fast): new contexts default to device_scale_factor=1 and reduced motion (the suite's own explicit
    values win). Software GL is much slower at 3x pixels. Suites that assert 3D or motion should not run with it;
  - a clear "machine too loaded" skip: BK_MAX_LOAD=<load per cpu> makes launch() print the reason and exit with code 77 (run_area.py
    reports it as SKIP, not as a failure) when load1 / cpus is above it.
Nothing here ever kills a process other than the browser this process started.
"""
from __future__ import annotations

import atexit
import glob
import os
import sys
import time

CPUS = os.cpu_count() or 1
BASE_ARGS = ["--no-sandbox", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-precise-memory-info"]
SKIP_CODE = 77


def load_ratio() -> float:
    try:
        return os.getloadavg()[0] / CPUS
    except OSError:
        return 0.0


def multiplier(ratio: float | None = None) -> float:
    """1 when the machine is calm (load per cpu <= 1.5), up to 6 when it is swamped"""
    r = load_ratio() if ratio is None else ratio
    return max(1.0, min(6.0, r / 1.5))


def chrome_exe():
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome", "/opt/pw-browsers/chromium/chrome-linux/chrome"):
        hit = sorted(glob.glob(pat))
        if hit:
            return hit[-1]
    return None


def too_loaded(max_ratio: float | None = None) -> str:
    """'' when fine, else the plain reason (for a skip)"""
    lim = max_ratio if max_ratio is not None else float(os.environ.get("BK_MAX_LOAD", "0") or 0)
    r = load_ratio()
    if lim and r > lim:
        return f"machine too loaded: load {os.getloadavg()[0]:.0f} on {CPUS} cpus ({r:.1f} per cpu, limit {lim:g}); run it when it is calmer"
    return ""


# ------------------------------------------------------------------------------------------------ patching Playwright (once)
_PATCHED = False
_TIMED = ("goto", "reload", "wait_for_function", "wait_for_selector", "wait_for_load_state", "wait_for_url", "click", "dblclick", "tap", "fill", "type", "press",
          "text_content", "inner_text", "inner_html", "get_attribute", "hover", "check", "uncheck", "select_option", "set_input_files", "focus")


def _scale_kw(kw: dict, mult: float) -> dict:
    t = kw.get("timeout")
    if isinstance(t, (int, float)) and t > 0 and mult > 1:
        kw = dict(kw)
        kw["timeout"] = int(t * mult)
    return kw


def install() -> None:
    """scale timeouts, retry a flaky wait once, optional fast defaults. Idempotent."""
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True
    from playwright.sync_api import Browser, BrowserContext, Page, TimeoutError as PWTimeout
    try:
        from playwright.sync_api import Frame, Locator
    except ImportError:  # pragma: no cover
        Frame = Locator = None

    def wrap_call(orig):
        def call(self, *a, **kw):
            m = multiplier()
            kw = _scale_kw(kw, m)
            try:
                return orig(self, *a, **kw)
            except PWTimeout:
                if m < 2 or os.environ.get("BK_RETRY", "1") == "0":
                    raise
                return orig(self, *a, **kw)          # one more try: a loaded machine often just needed a little longer
        call.__name__ = getattr(orig, "__name__", "call")
        return call

    for cls in (Page,) + ((Frame,) if Frame else ()):
        for name in _TIMED:
            if hasattr(cls, name):
                setattr(cls, name, wrap_call(getattr(cls, name)))
    if Locator:                                                  # page.locator(...).click() and friends: the same scaling and one retry
        for name in _TIMED + ("wait_for", "input_value", "scroll_into_view_if_needed", "screenshot"):
            if name not in ("goto", "reload", "wait_for_function", "wait_for_selector", "wait_for_load_state", "wait_for_url") and hasattr(Locator, name):
                setattr(Locator, name, wrap_call(getattr(Locator, name)))
    try:                                                         # expect(locator).to_be_visible() ...: default 5 s scaled, explicit timeouts scaled, one retry
        from playwright.sync_api import expect, LocatorAssertions, PageAssertions

        def wrap_assert(orig):
            def call(self, *a, **kw):
                m = multiplier()
                kw = _scale_kw(kw, m)
                try:
                    return orig(self, *a, **kw)
                except AssertionError:
                    if m < 2 or os.environ.get("BK_RETRY", "1") == "0":
                        raise
                    return orig(self, *a, **kw)
            return call
        for cls in (LocatorAssertions, PageAssertions):
            for name in [n for n in dir(cls) if n.startswith(("to_", "not_to_"))]:
                setattr(cls, name, wrap_assert(getattr(cls, name)))
        expect.set_options(timeout=int(5000 * multiplier()))
    except Exception:  # noqa: BLE001
        pass

    def scale_ctx(ctx):
        t = int(30000 * multiplier())
        try:
            ctx.set_default_timeout(t)
            ctx.set_default_navigation_timeout(t)
        except Exception:  # noqa: BLE001
            pass
        return ctx

    def fast(kw: dict) -> dict:
        if os.environ.get("BK_FAST") == "1":
            kw = dict(kw)
            kw.setdefault("device_scale_factor", 1)
            kw.setdefault("reduced_motion", "reduce")
        return kw

    orig_ctx = Browser.new_context
    Browser.new_context = lambda self, *a, **kw: scale_ctx(orig_ctx(self, *a, **fast(kw)))
    orig_page = Browser.new_page

    def new_page(self, *a, **kw):
        pg = orig_page(self, *a, **fast(kw))
        scale_ctx(pg.context)
        return pg
    Browser.new_page = new_page


# ------------------------------------------------------------------------------------------------ wall-clock limits
SCALED: list = []


def limit(seconds: float, label: str = "", cap: float | None = None) -> float:
    """a wall-clock limit for an assert: `seconds` on a quiet machine (exactly as written), seconds x multiplier when the load is high
    (multiplier >= 2). Said in the output whenever it was scaled, so a pass under load is never mistaken for a quiet-machine pass."""
    m = multiplier()
    if m < 2:
        return seconds
    out = round(seconds * m, 3)
    if cap is not None:                                 # never past what the assert exists to tell apart (e.g. a site that answers after 7 s)
        out = max(seconds, min(out, cap))
    note = f"limit {label or seconds} scaled {seconds:g} -> {out:g} (x{m:.1f}, load {load_ratio() * CPUS:.0f} on {CPUS} cpus)"
    if note not in SCALED:                               # said once per limit
        SCALED.append(note)
        print("   (BK) " + note, flush=True)
    return out


def limit_ms(ms: float, label: str = "", cap: float | None = None) -> float:
    return limit(ms / 1000.0, label or f"{ms:g} ms", None if cap is None else cap / 1000.0) * 1000.0


# ------------------------------------------------------------------------------------------------ the launch
class _Shared:
    """the browser of this Playwright instance; close() is a no-op (the real one runs at exit) so sections can share it"""

    def __init__(self, br):
        self._br = br

    def __getattr__(self, name):
        return getattr(self._br, name)

    def close(self):
        pass

    def really_close(self):
        try:
            self._br.close()
        except Exception:  # noqa: BLE001
            pass


_LIVE: dict = {}


def _alive(sh) -> bool:
    try:
        return bool(sh._br.is_connected())
    except Exception:  # noqa: BLE001
        return False


def launch(pw, args=None, **kw):
    """the shared, scaled browser. Same as pw.chromium.launch(...) for the suite (its args= and options are kept)."""
    why = too_loaded()
    if why:
        print(f"SKIP: {why}", flush=True)
        sys.exit(SKIP_CODE)
    install()
    merged = list(BASE_ARGS)
    for a in (args or []):
        if a not in merged:
            merged.append(a)
    key = (id(pw), tuple(merged), tuple(sorted((k, str(v)) for k, v in kw.items())))
    sh = _LIVE.get(key)
    if sh is not None and _alive(sh):
        return sh
    exe = chrome_exe()
    if exe and "executable_path" not in kw:
        kw["executable_path"] = exe
    last = None
    for _ in range(2):                                   # a launch that fails on a swamped machine is tried once more
        try:
            sh = _Shared(pw.chromium.launch(args=merged, **kw))
            _LIVE[key] = sh
            return sh
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2)
    raise last


@atexit.register
def _close_all():
    for sh in list(_LIVE.values()):
        sh.really_close()
