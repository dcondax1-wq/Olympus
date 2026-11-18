"""Hermetic browser tests by default (2026-11-18): every Playwright context the tests open answers ntfy.sh with an empty "{}".

Why: the owner's PC posts its live status to a PUBLIC ntfy topic (site/status_feed.json) and pc_feed.js (Home, Jarvis, the Board,
the Gate, the hubs, every app through olympus/truth.js withPcFeed) reads it. Without this a browser suite showed the REAL account
numbers instead of its fixtures (test_live_publish: "live . 6 min ago" instead of its live.json A / B).

    nothing to do in a suite: tests/__init__.py calls auto() (python -m tests.<suite>), browser_kit.install() and agora_kit call install()
    NS.stub(ctx_or_page)        # the same route by hand (a context made some other way)
    NS.stub(ctx, body)          # a fixture instead of "{}" (an ntfy /json?poll=1 answer = one JSON event per line)
    NET_STUB_OFF=1              # off (to compare a suite against the real feed); NET_STUB_LOG=<file> logs the stubbed calls

The route is registered when the context is made, so a suite's own later route (page.route / ctx.route "**/ntfy.sh/**" or "**/*")
still wins: Playwright tries the newest route first. "{}" has no message, so pc_feed.fetchLatest() gives null and the page falls back
to its home.json / data.json / live.json fixtures, as it does when the PC is silent. Node harnesses: tests/net_stub.cjs (the twin).
"""
from __future__ import annotations

import atexit
import importlib.abc
import importlib.util
import os
import sys

NTFY = "**/ntfy.sh/**"
EMPTY = "{}"
HITS: list = []          # urls the stub answered (a suite can assert on it)


@atexit.register
def _log():                # NET_STUB_LOG=<file>: one line per process, "<script> <ntfy calls stubbed>" (which suites the stub touched)
    out = os.environ.get("NET_STUB_LOG")
    if out:
        try:
            with open(out, "a", encoding="utf-8") as f:
                f.write(f"{os.path.basename(sys.argv[0] or '?')} {len(HITS)}\n")
        except OSError:
            pass


def stub(target, body: str = EMPTY):
    """route ntfy.sh on a BrowserContext or Page to `body` (default "{}"), CORS open, for GET and POST alike"""
    def answer(r):
        HITS.append(r.request.url)
        r.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body=body)
    target.route(NTFY, answer)
    return target


def install() -> None:
    """patch Browser.new_context / new_page and BrowserType.launch_persistent_context once (sync API). Idempotent across imports
    (tests.net_stub and net_stub are the same patch: the flag lives on the Playwright class)."""
    if os.environ.get("NET_STUB_OFF") == "1":          # only to see a suite as it was (the real feed): never in a normal run
        return
    try:
        from playwright.sync_api import Browser, BrowserType
    except Exception:  # noqa: BLE001  (no Playwright: nothing to patch)
        return
    if getattr(Browser, "_ntfy_stubbed", False):
        return
    Browser._ntfy_stubbed = True
    orig_ctx, orig_page, orig_pers = Browser.new_context, Browser.new_page, BrowserType.launch_persistent_context

    def new_context(self, *a, **kw):
        return stub(orig_ctx(self, *a, **kw))

    def new_page(self, *a, **kw):
        pg = orig_page(self, *a, **kw)
        stub(pg.context)
        return pg

    def launch_persistent_context(self, *a, **kw):
        return stub(orig_pers(self, *a, **kw))
    Browser.new_context, Browser.new_page, BrowserType.launch_persistent_context = new_context, new_page, launch_persistent_context


class _Hook(importlib.abc.MetaPathFinder):
    """runs install() right after playwright.sync_api is first imported (so importing tests/ never pays for Playwright)"""

    def find_spec(self, name, path, target=None):
        if name != "playwright.sync_api":
            return None
        sys.meta_path.remove(self)
        spec = importlib.util.find_spec(name)
        if spec is None or spec.loader is None:
            return spec
        loader, run = spec.loader, spec.loader.exec_module

        def exec_module(module):
            run(module)
            install()
        loader.exec_module = exec_module
        return spec


def auto() -> None:
    if "playwright.sync_api" in sys.modules:
        install()
    elif not any(isinstance(f, _Hook) for f in sys.meta_path):
        sys.meta_path.insert(0, _Hook())
