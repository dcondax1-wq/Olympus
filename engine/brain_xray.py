"""BRAIN X-RAY (day-brains-feed 2026-11-27): the gates of each strategy's decision, with the real number vs the rule, for the phone's
live brain view (tools/web_public/nq/brainview.js, the owner: "as the creator I want to see everything happening within the brain").

READ-ONLY: built in the 15-minute report task (tools/pc_report.full -> ext block "bx", after every other block: EXT_LAST) from what
the bots ALREADY computed and the heartbeat already carries. It never trades, sizes, arms or writes a file; never raises; no account
ids (none are read: the blocks below carry none) and no names.

  lit    hb["brain"] (engine/brain.compact): the forming setup per side (depth / displacement vs the rules), the newest setups with every
         check (key, pass, the check's own text cut short: it carries the number and the rule), how many were blocked, the sizing of
         the next trade (micros, $ risk, risk pts, $ at target), what blocks it (guards)
  atlas  hb["second"] (engine/second.compact): each routed lobe's stage, first failing check and its checks (name, pass, value, need)
         and its armed plan (side, entry, stop, target, $ risk, micros)
  blitz  hb["blitz"] (engine/blitz.compact, PAPER): its state line, today's signals and the band
Order flow (POSEIDON) already rides as "ofp" (engine/oflive.paper_tiny).

Shape (short keys, <= MAX_BYTES; fit() cuts it smaller, least loss first):
  {"v": 1, "t": hb t,
   "lit": {"st": stage key, "a": ATR, "p": price, "r": [depth rule, disp rule, min_rr],
           "w": [[side "L"|"S", stage, depth_atr, disp_atr, allowed 1|0]],
           "s": [[hm, side, status, first-fail key, [[key, 1|0, "value / rule"], ...]]],  newest last (short_check)
           "n": [setups today, blocked], "sz": [micros, $ risk, risk pts, $ at target, what], "gd": blocking text},
   "atlas": {"l": [[short, stage, first fail, [[name, 1|0, value, need], ...], [side, entry, stop, target, $ risk, micros] | null]]},
   "blitz": {"st": state line, "sg": [[hm, side, text]], "ok": band day ok}}
"""
from __future__ import annotations

import json
import re

VERSION = 1
MAX_BYTES = 1600           # the whole block; the ext post's room after every other block (pc_report EXT_LAST)
TXT = 70                   # a check's text


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _f(x, n=2):
    try:
        v = float(x)
        return round(v, n) if v == v else None
    except (TypeError, ValueError):
        return None


def _t(s, n=TXT) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


_RX = [
    ("depth", re.compile(r"([\d.]+) ATR = .*?needs >= ([\d.]+) ATR"), lambda m: f"{m[1]} / {m[2]} ATR"),
    ("disp", re.compile(r"body ([\d.]+) ATR \(needs >= ([\d.]+)"), lambda m: f"{m[1]} / {m[2]} ATR"),
    ("window", re.compile(r"entry bar (\d\d:\d\d) ET (?:inside|outside) (\d\d:\d\d-\d\d:\d\d)"), lambda m: f"{m[1]} in {m[2]}"),
    ("idm", re.compile(r"(\d+) swings? taken first.*?needs (\d+)"), lambda m: f"{m[1]} / {m[2]}"),
    ("stop", re.compile(r"= ([\d.]+) pts \(trades ([\d.]+)-([\d.]+)\)"), lambda m: f"{m[1]} pts ({m[2]}-{m[3]})"),
    ("target", re.compile(r"= ([\d.]+)R away \(needs >= ([\d.]+)R"), lambda m: f"{m[1]}R / {m[2]}R"),
    ("target", re.compile(r"only ([\d.]+)R away \(needs >= ([\d.]+)R"), lambda m: f"{m[1]}R / {m[2]}R"),
]


def short_check(key: str, text) -> str:
    """A LIT check's text -> "value / rule" ("0.39 / 0.5 ATR", "23.5R / 1.5R"); the text cut short when no pattern fits."""
    t = str(text or "")
    for k, rx, f in _RX:
        if k == key:
            m = rx.search(t)
            if m:
                return f(m)
    if key == "day":
        return "free" if "no trade yet" in t else "taken"
    if key == "monday":
        return "blocked" if "only" in t else "ok"
    return _t(t, 24)


def lit(b: dict | None) -> dict | None:
    b = _d(b)
    if not b or b.get("error"):
        return None
    st = b.get("stage")
    r = _d(b.get("rules"))
    out = {"st": _d(st).get("key") if isinstance(st, dict) else st, "a": _f(b.get("atr")), "p": _f(b.get("price")),
           "r": [_f(r.get("depth")), _f(r.get("disp")), _f(r.get("min_rr"))]}
    out["w"] = [["L" if str(w.get("side", "")).upper().startswith("L") else "S", str(w.get("stage") or "")[:14], _f(w.get("depth_atr")),
                 _f(w.get("disp")), 1 if w.get("allowed", True) else 0] for w in (_d(x) for x in _l(b.get("watch")))]
    S = []
    for s in _l(b.get("setups"))[-4:]:
        s = _d(s)
        ch = [[str(c[0])[:10], 1 if c[1] else 0, short_check(str(c[0]), c[2] if len(c) > 2 else "")] for c in _l(s.get("checks")) if isinstance(c, list) and len(c) >= 2]
        ff = next((c[0] for c in ch if not c[1]), "")
        S.append([str(s.get("hm") or ""), "L" if str(s.get("side", "")).upper().startswith("L") else "S", str(s.get("status") or "")[:10], ff, ch])
    out["s"] = S
    n = _d(b.get("setups_n"))
    out["n"] = [n.get("all"), n.get("blocked")]
    z = _d(b.get("sizing"))
    if z:
        out["sz"] = [z.get("qty"), _f(z.get("risk_usd"), 0), _f(z.get("risk_pts")), _f(z.get("win_usd"), 0), _t(z.get("what"), 60)]
    g = _d(b.get("guards"))
    if g.get("blocking"):
        out["gd"] = _t(g.get("blocking"), 80)
    return out


def atlas(sec: dict | None) -> dict | None:
    S = _d(_d(sec).get("strategies"))
    if not S:
        return None
    ab = _d(_d(_d(sec).get("route")).get("account_b"))
    keys = [k for k in _l(ab.get("keys")) if k in S] or [k for k, v in S.items() if _d(v).get("route")] or \
        [k for k, v in S.items() if _d(v).get("brain") and not _d(v).get("candidate")]
    L = []
    for k in keys[:3]:
        s = _d(S.get(k))
        b = _d(s.get("brain"))
        ch = [[_t(c.get("name") or c.get("k"), 34), 1 if c.get("ok") else 0, _t(c.get("val"), 18) if c.get("val") is not None else None,
               _t(c.get("need"), 18) if c.get("need") is not None else None] for c in (_d(x) for x in _l(b.get("checks")))][:6]
        p = _d(b.get("plan"))
        plan = [str(p.get("side") or ""), _f(p.get("entry")), _f(p.get("stop")), _f(p.get("target")), _f(p.get("risk_usd"), 0), p.get("qty_500")] if p else None
        stg = _d(s.get("state")).get("stage") or b.get("stage")
        L.append([str(s.get("short") or k)[:8], str(stg or "")[:12], _t(b.get("first_fail"), 60), ch, plan])
    return {"l": L} if L else None


def blitz(bz: dict | None) -> dict | None:
    bz = _d(bz)
    if not bz or not bz.get("paper"):
        return None
    sg = [[str(x.get("hm") or x.get("time") or "")[:5], str(x.get("side") or x.get("dir") or "")[:5], _t(x.get("text") or x.get("why") or x.get("note"), 50)]
          for x in (_d(y) for y in _l(bz.get("signals"))[-3:])]
    band = _d(bz.get("band"))
    return {"st": _t(bz.get("state"), 100), "sg": sg, "ok": band.get("day_ok")}


def build(hb: dict | None) -> dict | None:
    """The ext block "bx"; None when the heartbeat has none of the three brains. Never raises."""
    try:
        hb = _d(hb)
        out = {"v": VERSION, "t": hb.get("t")}
        for k, f, src in (("lit", lit, hb.get("brain")), ("atlas", atlas, hb.get("second")), ("blitz", blitz, hb.get("blitz"))):
            try:
                v = f(src)
            except Exception:  # noqa: BLE001 - one broken brain never hides the others
                v = None
            if v:
                out[k] = v
        if len(out) <= 2:
            return None
        return fit(out, MAX_BYTES)
    except Exception:  # noqa: BLE001
        return None


def size(o) -> int:
    return len(json.dumps(o, separators=(",", ":"), default=str))


def fit(o: dict, max_bytes: int = MAX_BYTES) -> dict:
    """Smaller, least loss first: check texts shortened, older setups, ATLAS checks, BLITZ signals, then the texts out."""
    if not isinstance(o, dict):
        return o
    L, A, B = _d(o.get("lit")), _d(o.get("atlas")), _d(o.get("blitz"))
    steps = [lambda: _l(L.get("sz"))[4:5] and L["sz"].__setitem__(4, _t(L["sz"][4], 30)),   # the size's sentence first
             lambda: L.__setitem__("s", _l(L.get("s"))[-3:]) if L else None,                  # then the oldest setup (the newest keep their numbers)
             lambda: B.__setitem__("sg", []) if B else None,
             lambda: [c.__setitem__(0, _t(c[0], 24)) for x in _l(A.get("l")) for c in _l(x[3])],
             lambda: L.__setitem__("s", _l(L.get("s"))[-2:]) if L else None,
             lambda: [c.__setitem__(2, _t(c[2], 16)) for s in _l(L.get("s")) for c in _l(s[4]) if len(c) > 2],
             lambda: [x.__setitem__(3, _l(x[3])[:3]) for x in _l(A.get("l"))],
             lambda: [c.__setitem__(2, "") for s in _l(L.get("s")) for c in _l(s[4]) if len(c) > 2],
             lambda: L.__setitem__("s", _l(L.get("s"))[-1:]) if L else None,
             lambda: [x.__setitem__(3, []) for x in _l(A.get("l"))],
             lambda: o.pop("blitz", None)]
    for st in steps:
        if size(o) <= max_bytes:
            break
        st()
    return o
