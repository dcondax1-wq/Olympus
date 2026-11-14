"""Turn the HTML pages into PNG images (and the report into a PDF) with a Chromium the machine already has.

Order tried, first that works:
  1. Playwright for Python with its Chromium (the cloud machine: /opt/pw-browsers), or Playwright driving installed Edge / Chrome;
  2. no Playwright: the browser itself in headless mode (`msedge --headless --screenshot`, which every Windows 10/11 PC has),
     one page at a time, so the owner's PC needs nothing installed;
  3. nothing found: the pages stay as HTML and the tool says so (open them in any browser).
Nothing here touches the network: every page is self-contained (fonts as data URIs) and loaded from disk or from memory.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time

WIN_BROWSERS = [r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe", r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
                r"%ProgramFiles%\Google\Chrome\Application\chrome.exe", r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                r"%LocalAppData%\Google\Chrome\Application\chrome.exe"]
MAC_BROWSERS = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "/Applications/Chromium.app/Contents/MacOS/Chromium"]


def short_tmp() -> str:
    """Chromium puts a socket in the temp folder and a Unix socket path must stay under 108 characters: with a very long TMPDIR
    (some sandboxes) the browser cannot start, so use /tmp then. Windows and normal Linux / macOS temp folders are untouched."""
    base = tempfile.gettempdir()
    if os.name != "nt" and len(base) > 40 and os.path.isdir("/tmp") and os.access("/tmp", os.W_OK):
        return "/tmp"
    return base


def pw_chromium() -> str | None:
    for pat in ("/opt/pw-browsers/chromium-*/chrome-linux/chrome", "/opt/pw-browsers/chromium/chrome-linux/chrome"):
        hit = sorted(glob.glob(pat))
        if hit:
            return hit[-1]
    return None


def system_browser() -> str | None:
    env = os.environ.get("AGENCY_BROWSER")
    if env and os.path.isfile(env):
        return env
    cands = []
    if os.name == "nt":
        cands = [os.path.expandvars(p) for p in WIN_BROWSERS]
    elif sys.platform == "darwin":
        cands = list(MAC_BROWSERS)
    else:
        cands = [pw_chromium() or ""] + [shutil.which(n) or "" for n in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge")]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


class Renderer:
    """with Renderer() as r: r.png(html, path, w, h); r.pdf(html, path)"""

    def __init__(self, prefer: str = "auto"):
        self.kind, self.detail = "none", ""
        self._pw = self._br = self._page = None
        self._tmp = None
        if short_tmp() != tempfile.gettempdir():                       # see short_tmp(): the browser's own temp files
            os.environ["TMPDIR"] = short_tmp()
            tempfile.tempdir = None
        if prefer in ("auto", "playwright"):
            try:
                from playwright.sync_api import sync_playwright
                self._pw = sync_playwright().start()
                errors = []
                for how in ("bundled", "default", "msedge", "chrome"):
                    try:
                        args = ["--no-sandbox"] if os.name != "nt" else []
                        if how == "bundled":
                            exe = pw_chromium()
                            if not exe:
                                continue
                            self._br = self._pw.chromium.launch(executable_path=exe, args=args)
                        elif how == "default":
                            self._br = self._pw.chromium.launch(args=args)
                        else:
                            self._br = self._pw.chromium.launch(channel=how, args=args)
                        self.kind, self.detail = "playwright", how
                        break
                    except Exception as e:  # noqa: BLE001
                        errors.append(f"{how}: {str(e).splitlines()[0][:120]}")
                if self._br is None:
                    self._pw.stop()
                    self._pw = None
            except Exception:  # noqa: BLE001  (no playwright package)
                self._pw = None
        if self.kind == "none" and prefer in ("auto", "cli"):
            exe = system_browser()
            if exe:
                self.kind, self.detail = "cli", exe
        if self.kind == "cli":
            self._tmp = tempfile.mkdtemp(prefix="agency_render_")

    # ------------------------------------------------------------------------------------------------------------ context
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        try:
            if self._br is not None:
                self._br.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._br = self._pw = self._page = None
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None

    @property
    def ok(self) -> bool:
        return self.kind != "none"

    # -------------------------------------------------------------------------------------------------------------- pages
    def _pg(self, w: int, h: int):
        if self._page is None:
            ctx = self._br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
            ctx.route("**/*", lambda route: route.abort() if route.request.url.startswith(("http://", "https://")) else route.continue_())
            self._page = ctx.new_page()
        else:
            self._page.set_viewport_size({"width": w, "height": h})
        return self._page

    def png(self, html_text: str, out: str, w: int, h: int) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        if self.kind == "playwright":
            pg = self._pg(w, h)
            pg.set_content(html_text, wait_until="load")
            try:
                pg.wait_for_function("document.documentElement.getAttribute('data-ready') === '1'", timeout=20000)
            except Exception:  # noqa: BLE001  (a page without the fit script)
                pass
            pg.screenshot(path=out, clip={"x": 0, "y": 0, "width": w, "height": h})
            return
        if self.kind == "cli":
            src = os.path.join(self._tmp, f"p{time.time_ns()}.html")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(html_text)
            for _ in range(2):                                         # a stale file must never pass for a new one; one retry
                if os.path.exists(out):
                    os.remove(out)
                self._cli(["--screenshot=" + os.path.abspath(out), f"--window-size={w},{h}"], src)
                if os.path.isfile(out):
                    break
            os.remove(src)
            if not os.path.isfile(out):
                raise RuntimeError(f"the browser made no image ({self.detail})")
            return
        raise RuntimeError("no browser to draw the images: install Microsoft Edge or Google Chrome")

    def full_png(self, path_or_html: str, out: str, w: int, is_file: bool = True, max_h: int = 12000, h_hint: int = 2600) -> None:
        """a whole page, any height (the contact sheet preview)"""
        if self.kind == "playwright":
            pg = self._pg(w, 900)
            if is_file:
                pg.goto("file://" + os.path.abspath(path_or_html).replace("\\", "/"), wait_until="load")
            else:
                pg.set_content(path_or_html, wait_until="load")
            try:
                pg.wait_for_function("document.documentElement.getAttribute('data-ready') === '1'", timeout=20000)
            except Exception:  # noqa: BLE001
                pass
            h = min(max_h, pg.evaluate("Math.ceil(document.documentElement.scrollHeight)"))
            pg.set_viewport_size({"width": w, "height": h})
            pg.wait_for_timeout(150)
            pg.screenshot(path=out, full_page=False, clip={"x": 0, "y": 0, "width": w, "height": h})
            return
        if self.kind == "cli":
            src = path_or_html
            if not is_file:
                src = os.path.join(self._tmp, f"p{time.time_ns()}.html")
                with open(src, "w", encoding="utf-8") as fh:
                    fh.write(path_or_html)
            h = min(max_h, h_hint)
            if os.path.exists(out):
                os.remove(out)
            self._cli(["--screenshot=" + os.path.abspath(out), f"--window-size={w},{h}"], src)
            return
        raise RuntimeError("no browser")

    def pdf(self, html_text: str, out: str) -> None:
        if self.kind == "playwright":
            pg = self._pg(816, 1056)
            pg.set_content(html_text, wait_until="load")
            try:
                pg.wait_for_function("document.documentElement.getAttribute('data-ready') === '1'", timeout=20000)
            except Exception:  # noqa: BLE001
                pass
            pg.emulate_media(media="print")
            pg.pdf(path=out, format="Letter", print_background=True, prefer_css_page_size=True)
            pg.emulate_media(media="screen")
            return
        if self.kind == "cli":
            src = os.path.join(self._tmp, f"r{time.time_ns()}.html")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(html_text)
            if os.path.exists(out):
                os.remove(out)
            self._cli(["--print-to-pdf=" + os.path.abspath(out), "--no-pdf-header-footer", "--print-to-pdf-no-header"], src)
            return
        raise RuntimeError("no browser")

    def _cli(self, extra: list, src: str) -> None:
        args = [self.detail, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1", "--no-first-run",
                "--disable-extensions", "--virtual-time-budget=6000", "--run-all-compositor-stages-before-draw",
                f"--user-data-dir={os.path.join(self._tmp, 'profile')}"]
        if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0:
            args.append("--no-sandbox")
        url = "file:///" + os.path.abspath(src).replace("\\", "/").lstrip("/")
        subprocess.run(args + extra + [url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120, check=False)


def png_size(path: str) -> tuple[int, int]:
    """(width, height) from the PNG header, no imaging library needed"""
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
