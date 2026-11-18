"""The PC status feed reader (Python twin of tools/web_public/pc_feed.js parseLatest; owner 2026-11-18 "split the ntfy post").

The PC (tools/pc_report.py) posts two kinds of message to the public ntfy status topic (status_feed.json):
  core  kind "le-live"      every run (15 min): t (the bot's heartbeat), pc, pc_verdict, reporter, board cards, accounts.
                            Always complete and small; the cloud PC-silent check (tools/pc_silent_check.feed_last) reads only this.
  ext   kind "le-live-ext"  every 2nd run, or at once when its news changed: "x" = the extra blocks (brd, life, mf, board_trades,
                            glance, kalshi_rewards, later the learning loop / ZEUS Lab notes), up to EXT_PARTS parts ("part" / "of"),
                            each under 3,900 bytes. Posted just BEFORE the core, so ntfy's since=latest is still the core.
merge(core, exts) lays each ext block into the core where the core has none ("glance" -> pc.glance, "board_trades" -> board.trades,
the rest top level), so every page sees the same shape as the old single post. Per part the newest ext wins whole. An old single
post (blocks inside, no ext) comes back unchanged. An ext older than EXT_MAX_AGE_S before the core is ignored. Stdlib only.
  pick(msgs)          -> the merged newest status of ntfy message dicts ({"message": "<json>", "time": ...}), or None
  merge(core, exts)   -> a merged copy of core
Tests: tests/test_live_publish.py (split / merge), tests/test_board.py, tests/test_bots_back.py (the JS twin).
"""
from __future__ import annotations

import copy
import json

CORE_KIND = "le-live"
EXT_KIND = "le-live-ext"
EXT_MAX_AGE_S = 2 * 3600
NESTED = {"glance": ("pc", "glance"), "board_trades": ("board", "trades")}   # ext key -> where in the core (an existing dict only)
CORE_OWN = ("v", "kind", "lite", "src", "t", "every_s", "trimmed", "pc", "pc_verdict", "reporter", "board", "accounts", "host",
            "model_state", "price", "day_pnl", "xt", "ext_t")


def _d(x):
    return x if isinstance(x, dict) else {}


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return v if v == v and v not in (float("inf"), float("-inf")) else 0.0


def rt(j, m=None) -> float:
    """When the PC looked (reporter.t / ext rt), else the ntfy time, else t."""
    j = _d(j)
    return _f(_d(j.get("reporter")).get("t")) or _f(j.get("rt")) or _f(_d(m).get("time")) or _f(j.get("t"))


def merge(core, exts=()):
    if not isinstance(core, dict):
        return core
    out = copy.deepcopy(core)
    crt = rt(core)
    seen, used = set(), 0.0
    for e in sorted([e for e in exts or () if isinstance(e, dict) and e.get("kind") == EXT_KIND], key=rt, reverse=True):
        et = rt(e)
        if not et or (crt and et < crt - EXT_MAX_AGE_S):
            continue
        part = e.get("part") or 0
        if part in seen:
            continue
        seen.add(part)
        for k, v in _d(e.get("x")).items():
            if k in NESTED:
                hk, kk = NESTED[k]
                host = out.get(hk)
                if isinstance(host, dict) and host.get(kk) is None:
                    host[kk] = copy.deepcopy(v)
                    used = max(used, et)
            elif k not in CORE_OWN and out.get(k) is None:
                out[k] = copy.deepcopy(v)
                used = max(used, et)
    if used:
        out["ext_t"] = int(used)
    return out


def pick(msgs):
    best, bt, exts = None, -1.0, []
    for m in msgs or []:
        if not isinstance(m, dict) or m.get("event", "message") != "message":
            continue
        try:
            j = json.loads(m.get("message") or "")
        except (ValueError, TypeError):
            continue
        if not isinstance(j, dict):
            continue
        if j.get("kind") == EXT_KIND:
            if not j.get("rt") and m.get("time"):
                j["rt"] = m["time"]
            exts.append(j)
        elif j.get("kind") == CORE_KIND and _f(j.get("t")) > 0:
            r = rt(j, m)
            if r >= bt:
                best, bt = j, r
    return merge(best, exts) if best else None
