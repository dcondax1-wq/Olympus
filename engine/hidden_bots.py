"""Hidden bots: the ONE switch that keeps a bot off every dashboard while its code, data and paper ledger keep running.

Owner 2026-11-15: "we are keeping Zlarior and ATLAS only for now; get rid of BLITZ on the dashboard, just know it's still
there". The switch is dashboard_view.json at the repo root:

    {"hidden_bots": ["blitz"]}      default (also when the file or the key is missing)
    {"hidden_bots": []}             BLITZ back on every page (next publish; the phone picks it up on its next open)

What hiding does (read-only; nothing here touches an engine, a ledger, an order or a state file):
  * published JSON is scrubbed: data.json / home.json (engine/live_board.site_block, the last helper the site build calls
    before it writes them), the PC's live.json / liveview.json / holo.json / holo_hist.json (engine/live_publish), and the PC
    dashboard's GET /api/* answers (ScrubMiddleware in server.py). Every file carries "hidden_bots" so the pages know.
  * the pages hide what is left (window.OLY_HIDDEN in tools/web_public/index.html, jarvis/index.html, web_next/index.html).
  * phone pushes stop: BLITZ PAPER notices are recorded only (engine/blitz.push_on), account C's paper / Sim pushes are
    logged only (engine/account_c); a REAL-money push of account C (only if the owner ever arms it) is never silenced.
Real money is never hidden: when this PC has account C armed (data/account_c.json "armed": true), BLITZ shows whatever the
switch says (real_money_c).
The engine keeps running exactly as before (engine/blitz.py PAPER shadow, the cloud's "blitz" state, the heartbeat blocks).
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, "dashboard_view.json")
DEFAULT = ("blitz",)
FORCE = None            # tests only: a tuple here replaces the file's list (e.g. () = nothing hidden)

# per bot: the dict keys that hold it, the identity values of its list items, the prefixes of its ids / keys / titles
BOTS = {
    "blitz": {
        "keys": {"blitz", "account_c", "acct_c", "acctc", "scalp", "pc_blitz"},
        "ids": {"blitz", "scalp", "account_c", "acct_c", "acctc", "pc_blitz", "strategy 3"},
        "prefixes": ("blitz", "scalp:blitz", "acctc:", "acctc_", "pc_blitz", "account_c"),
    },
}
ID_FIELDS = ("id", "key", "bot", "acct", "account", "account_id", "stage", "strategy", "strat", "kind", "source", "src", "trade",
             "sat", "lane", "app", "name", "setup", "title", "label", "lead")
KEEP_KEYS = {"hidden_bots"}


def hidden(path: str | None = None) -> tuple:
    """The hidden bots (lower case). Missing / broken file or key -> DEFAULT. Never raises."""
    if FORCE is not None and path is None:
        return tuple(FORCE)
    out = DEFAULT
    try:
        with open(path or CFG_PATH, encoding="utf-8") as fh:
            v = json.load(fh).get("hidden_bots")
        if isinstance(v, list):
            out = tuple(str(x).strip().lower() for x in v if str(x).strip())
    except Exception:
        pass
    if "blitz" in out and real_money_c():
        out = tuple(b for b in out if b != "blitz")     # real money is never hidden (account C armed on a real account)
    return out


def real_money_c(root: str | None = None) -> bool:
    """True when this PC has account C (BLITZ's own account, data/account_c.json) ARMED for real money: then BLITZ is shown
    whatever the switch says, so a real position is never off the dashboard. Never raises."""
    try:
        with open(os.path.join(root or ROOT, "data", "account_c.json"), encoding="utf-8") as fh:
            blk = (json.load(fh) or {}).get("account_c")
        return isinstance(blk, dict) and blk.get("armed") is True
    except Exception:
        return False


def is_hidden(bot: str = "blitz", path: str | None = None, hide=None) -> bool:
    h = hidden(path) if hide is None else tuple(hide)
    return str(bot or "").strip().lower() in h


def _rules(hide):
    keys, ids, pre = set(), set(), ()
    for b in hide:
        r = BOTS.get(b) or {"keys": {b}, "ids": {b}, "prefixes": (b,)}
        keys |= r["keys"]
        ids |= r["ids"]
        pre += tuple(r["prefixes"])
    return keys, ids, pre


def _hit(v, ids, pre) -> bool:
    if not isinstance(v, str):
        return False
    s = v.strip().lower()
    return bool(s) and (s in ids or s.startswith(pre))


def _item_hidden(x, ids, pre) -> bool:
    if isinstance(x, dict):
        return any(_hit(x.get(f), ids, pre) for f in ID_FIELDS)
    if isinstance(x, str):
        return _hit(x, ids, pre)
    return False


_SEPS = (" \u00b7 ", " | ", "; ")


def _text(s: str, ids, pre) -> str:
    """A summary line "Zlarior: ... · ATLAS ...: ... · BLITZ paper: ..." without its hidden bots' parts (a line that is all
    about one hidden bot stays as it is: its holder is dropped by the key / item rules)."""
    for sep in _SEPS:
        if sep in s:
            parts = s.split(sep)
            keep = [p for p in parts if not _hit(p, ids, pre)]
            if keep and len(keep) < len(parts):
                s = sep.join(keep)
    return s


def scrub(obj, hide=None):
    """A copy of obj without the hidden bots: dict keys that hold one ("blitz", "account_c", "scalp", "blitz_*") and list items
    whose id / key / bot / acct / kind / title ... names one. hide=None reads the switch; () returns obj unchanged."""
    hide = hidden() if hide is None else tuple(hide)
    if not hide:
        return obj
    keys, ids, pre = _rules(hide)

    def go(o):
        if isinstance(o, dict):
            return {k: go(v) for k, v in o.items()
                    if str(k) in KEEP_KEYS or not (str(k).lower() in keys or str(k).lower().startswith(pre))}
        if isinstance(o, (list, tuple)):
            return [go(v) for v in o if not _item_hidden(v, ids, pre)]
        if isinstance(o, str):
            return _text(o, ids, pre)
        return o
    return go(obj)


def scrub_inplace(obj, hide=None):
    """scrub() that edits obj itself (dicts and lists are changed in place, so every other holder of the same objects, e.g.
    the site build's home.json made from data.json's parts, sees the result). Returns obj."""
    hide = hidden() if hide is None else tuple(hide)
    if not hide:
        return obj
    keys, ids, pre = _rules(hide)
    seen = set()

    def go(o):
        if id(o) in seen:
            return
        if isinstance(o, dict):
            seen.add(id(o))
            for k in [k for k in o if str(k) not in KEEP_KEYS and (str(k).lower() in keys or str(k).lower().startswith(pre))]:
                del o[k]
            for k, v in list(o.items()):
                if isinstance(v, str):
                    o[k] = _text(v, ids, pre)
                else:
                    go(v)
        elif isinstance(o, list):
            seen.add(id(o))
            o[:] = [_text(v, ids, pre) if isinstance(v, str) else v for v in o if not _item_hidden(v, ids, pre)]
            for v in o:
                go(v)
    go(obj)
    return obj


def stamp(obj: dict, hide=None) -> dict:
    """obj with "hidden_bots" (the pages read it; [] = nothing hidden)."""
    if isinstance(obj, dict):
        obj["hidden_bots"] = list(hidden() if hide is None else hide)
    return obj


def publish(obj, hide=None):
    """scrub + stamp: what every publisher calls on a file it is about to write."""
    hide = hidden() if hide is None else tuple(hide)
    out = scrub(obj, hide)
    return stamp(out, hide) if isinstance(out, dict) else out


class ScrubMiddleware:
    """Pure ASGI middleware for the PC dashboard (server.py): GET /api/* JSON answers go out without the hidden bots.
    /api/next/blitz and /api/next/start/blitz* (the bot's own page and switches) answer as before, so it can come back."""

    def __init__(self, inner, hide_fn=hidden):
        self.inner = inner
        self.hide_fn = hide_fn

    async def __call__(self, scope, receive, send):
        path = scope.get("path") or ""
        if scope.get("type") != "http" or scope.get("method") != "GET" or not path.startswith("/api/") or "blitz" in path:
            return await self.inner(scope, receive, send)
        try:
            hide = tuple(self.hide_fn())
        except Exception:
            hide = DEFAULT
        if not hide:
            return await self.inner(scope, receive, send)
        start, body, mode = {}, [], {}

        async def _send(msg):
            t = msg.get("type")
            if t == "http.response.start":
                hdrs = msg.get("headers") or []
                ctype = next((v for k, v in hdrs if k.lower() == b"content-type"), b"") or b""
                enc = next((v for k, v in hdrs if k.lower() == b"content-encoding"), b"") or b""
                mode["json"] = b"json" in ctype.lower() and not enc       # anything else (a stream, a file) passes untouched
                if not mode["json"]:
                    return await send(msg)
                start.update(msg)
                return
            if t == "http.response.body" and mode.get("json"):
                body.append(msg.get("body") or b"")
                if msg.get("more_body"):
                    return
                raw = b"".join(body)
                try:
                    raw = json.dumps(publish(json.loads(raw.decode("utf-8")), hide), separators=(",", ":"),
                                     default=str).encode("utf-8")
                except Exception:
                    pass
                hdrs = [(k, v) for k, v in start.get("headers") or [] if k.lower() != b"content-length"]
                await send({**start, "headers": hdrs + [(b"content-length", str(len(raw)).encode())]})
                await send({"type": "http.response.body", "body": raw})
                return
            await send(msg)
        await self.inner(scope, receive, _send)
