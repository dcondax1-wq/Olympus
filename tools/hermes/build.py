"""Write OLYMPUS Wrapped's files: wrapped.json (the stories' numbers) and jarvis.json (the Jarvis card).

  python -m tools.hermes.build --site site            from a built site (its data.json + home.json) -> site/hermes/
  python -m tools.hermes.build --site site --live live.json    + the PC's live.json (fresher Mind lessons)
  python -m tools.hermes.build --demo                 the demo (tools/hermes/fixture.py) -> tools/web_public/hermes/

The cloud publish runs it through tools/build_web_dashboard.py (publish(out), right after the app folders are copied,
guarded: a failure only prints a line). A site without data.json keeps the page's demo files, which say DEMO.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.hermes import fixture, wrapped  # noqa: E402

PAGE = os.path.join(ROOT, "tools", "web_public", "hermes")
MAX_WRAPPED = 64 * 1024
MAX_CARD = 8 * 1024


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def dumps(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def _write(path: str, text: str) -> None:
    """Atomic: the page never reads half a file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def write(out_dir: str, w: dict, demo_copy: bool = False) -> dict:
    """wrapped.json + jarvis.json into out_dir (+ demo.json when demo_copy). Returns their sizes."""
    body, card = dumps(w), dumps(wrapped.jarvis_card(w))
    if len(body.encode()) > MAX_WRAPPED:
        raise ValueError(f"wrapped.json is {len(body.encode())} bytes (cap {MAX_WRAPPED})")
    if len(card.encode()) > MAX_CARD:
        raise ValueError(f"jarvis.json is {len(card.encode())} bytes (cap {MAX_CARD})")
    _write(os.path.join(out_dir, "wrapped.json"), body)
    _write(os.path.join(out_dir, "jarvis.json"), card)
    if demo_copy:
        _write(os.path.join(out_dir, "demo.json"), body)
    return {"wrapped": len(body.encode()), "jarvis": len(card.encode())}


def demo() -> dict:
    return wrapped.build(fixture.data(), fixture.home(), None, now=fixture.NOW, demo=True)


def publish(site: str, now: float | None = None, live_path: str | None = None) -> dict | None:
    """<site>/hermes/wrapped.json + jarvis.json from <site>/data.json (+ home.json). None when the site has no data.json."""
    data = _load(os.path.join(site, "data.json"))
    if not isinstance(data, dict):
        return None
    home = _load(os.path.join(site, "home.json"))
    live = _load(live_path) if live_path else None
    w = wrapped.build(data, home if isinstance(home, dict) else None, live if isinstance(live, dict) else None,
                      now=now if now is not None else time.time())
    return write(os.path.join(site, "hermes"), w)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", help="a built site folder (data.json, home.json)")
    ap.add_argument("--live", help="the PC's live.json (optional)")
    ap.add_argument("--now", type=float, help="unix seconds (default: now)")
    ap.add_argument("--demo", action="store_true", help="write the demo files to tools/web_public/hermes/")
    a = ap.parse_args(argv)
    if a.demo:
        print("demo ->", PAGE, write(PAGE, demo(), demo_copy=True))
        return 0
    if not a.site:
        ap.error("--site or --demo")
    res = publish(a.site, a.now, a.live)
    print("hermes ->", os.path.join(a.site, "hermes"), res if res else "(no data.json: the demo stays)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
