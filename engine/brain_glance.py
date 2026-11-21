"""Brain glance (2026-11-17, owner: "a whole brain page where I see what's going on"; read-only, never trades).

One small block per bot and account for the phone's Brain page (tools/web_public/brain.js "All bots" tab): on / off,
armed, the levels it watches, the setups armed right now and what would trigger them, the last decision and why there
was no trade (plain words), the open trade with $ risk and $ target, today's $ and the room left, the last thought-log
lines. Built from what the heartbeat already carries (engine/heartbeat.Heartbeat.payload: brain, second, acct, health)
plus the live board's account cards (engine/live_board.build: today's $, room, position), so it adds no work to the bot.

Bots: Zlarior (LIT, the 50K), ATLAS (the 25K), Rapid EOD (only when data/rapid.json names an account: the extra account
with lane "rapid" in acct.accounts). BLITZ is never in it (hidden, paper: owner 2026-11-16).

It rides on the PC's 15-minute status (tools/pc_report.lite -> pc.glance, under MAX_BYTES) and the heartbeat / live.json
(engine/heartbeat "glance"), so the phone shows it even without GitHub.

    python -X utf8 -m engine.brain_glance [heartbeat.json]      prints the glance of a heartbeat file
"""
from __future__ import annotations

import json
import re
import sys
import time

VERSION = 2                  # v2 (day-nqdash3 2026-11-21, the NQ Brain page): px, chk, blk (LIT); lobes, dll, dll_used, lv distances (ATLAS)
MAX_BYTES = 1700
USD_PT = 2.0                 # MNQ: $2 a point a micro
ARMED_ST = ("armed", "tapped", "entering")
LOBE_ST = {"waiting": "window", "armed": "armed", "in_trade": "trade", "done": "done", "off": "off", "error": "off"}
LOG_N = 8                    # the longer thought stream (pc_report ext block "glog"; the glance itself keeps 4 a bot)


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _f(x, d=None):
    try:
        v = float(x)
        return v if v == v and abs(v) != float("inf") else d
    except (TypeError, ValueError):
        return d


def _t(s, n=140) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _px(v) -> str:
    v = _f(v)
    return "-" if v is None else f"{v:,.2f}"


def _usd(v) -> int | None:
    v = _f(v)
    return None if v is None else int(round(v))


def _pos(p, risk=None, tgt=None) -> dict | None:
    """The open trade with $ risk and $ target (points x $2 x micros when the bot did not say)."""
    p = _d(p)
    if not p:
        return None
    q, e, s, g = _f(p.get("qty")), _f(p.get("entry")), _f(p.get("stop")), _f(p.get("target"))
    side = str(p.get("side") or ("LONG" if (_f(p.get("dir"), 0) or 0) > 0 else "SHORT")).upper()
    if risk is None and None not in (q, e, s):
        risk = abs(e - s) * USD_PT * q
    if tgt is None and None not in (q, e, g):
        tgt = abs(g - e) * USD_PT * q
    out = {"side": side, "qty": int(q) if q is not None else None, "entry": e, "stop": s, "target": g,
           "risk_usd": _usd(_f(p.get("risk_usd"), risk)), "tgt_usd": _usd(_f(p.get("target_usd"), tgt)),
           "now_usd": _usd(_f(p.get("unrealized_usd"), _f(p.get("usd_now"))))}
    return {k: v for k, v in out.items() if v is not None}


def _lit_levels(br) -> list:
    """[label, price, points away] of the nearest untaken levels: up to 3 above and 3 below."""
    n = _d(br.get("nearest"))
    rows = []
    for side in ("above", "below"):
        for r in _l(n.get(side))[:3]:
            if isinstance(r, dict) and _f(r.get("price")) is not None:
                rows.append([_t(r.get("label"), 28), round(_f(r["price"]), 2), round(_f(r.get("dist"), 0), 1)])
    return rows


def _lit_armed(br) -> list:
    out = []
    for s in reversed(_l(br.get("setups"))):
        if not isinstance(s, dict) or s.get("status") not in ARMED_ST:
            continue
        pl = _d(s.get("plan"))
        side = str(s.get("side") or "")
        lim = pl.get("limit")
        if s.get("status") == "tapped":
            trig = f"Limit {_px(lim)} was touched: it enters on the next 1-minute close back the {'up' if side == 'LONG' else 'down'} way (1m CISD)."
        elif s.get("status") == "entering":
            trig = "Entering now at market (the 1m CISD just closed)."
        else:
            trig = (f"Enters if price comes back to {_px(lim)} before {pl.get('expires_hm') or 'the window ends'} ET, "
                    "then a 1-minute close back its way.")
        out.append({"side": side, "text": _t(f"stop {_px(pl.get('stop'))} · target {_px(pl.get('target'))}"
                                              + (f" ({_f(pl.get('rr'), 0):.1f}R)" if pl.get("rr") is not None else ""), 90),
                    "trig": _t(trig, 150)})
        if len(out) >= 2:
            break
    if not out and _d(br.get("stage")).get("key") not in ("done", "closed", "trade"):
        # nothing armed: what the forming leg still needs (the Brain's "watch")
        for w in _l(br.get("watch")):
            if isinstance(w, dict) and w.get("text") and w.get("allowed", True):
                out.append({"side": str(w.get("side") or ""), "text": "forming", "trig": _t(w.get("text"), 150)})
    return out[:2]


def _lit_why(br) -> str:
    """The last decision in plain words, and why there was no trade."""
    st = _d(br.get("stage"))
    if br.get("trade"):
        return "In a trade: " + _t(st.get("waiting"), 140)
    for s in reversed(_l(br.get("setups"))):
        if not isinstance(s, dict):
            continue
        if s.get("status") in ("rejected", "no_fill", "blocked"):
            fail = next((c for c in _l(s.get("checks")) if isinstance(c, (list, tuple)) and len(c) >= 3 and not c[1]), None)
            why = (fail[2] if fail else "") or s.get("status_text") or s.get("status")
            return _t(f"{s.get('hm') or ''} {s.get('side') or ''} setup, no trade: {why}", 170)
        if s.get("status") == "filled":
            tr = _d(s.get("trade"))
            r = _f(tr.get("r"))
            res = (" (" + str(tr.get("exit")) + ("" if r is None else " %+.2fR" % r) + ")") if tr.get("exit") else ""
            return _t(f"{s.get('hm') or ''} {s.get('side') or ''} setup traded{res}. One trade a day: done until tomorrow.", 170)
        break
    g = _l(_d(br.get("guards")).get("blocking"))
    if g:
        return _t("No new trade: " + "; ".join(str(x) for x in g), 170)
    return _t("No setup yet today. " + str(st.get("waiting") or ""), 170)


def _log(rows, n=4) -> list:
    out = []
    for r in _l(rows)[:n]:
        if isinstance(r, dict) and r.get("text"):
            out.append([str(r.get("hm") or ""), _t(r.get("text"), 120)])
    return out


def lit(hb: dict, card: dict | None) -> dict:
    hb, c = _d(hb), _d(card)
    br = _d(hb.get("brain"))
    acc = _d(_d(hb.get("health")).get("account"))
    st = _d(br.get("stage"))
    out = {"id": "lit", "name": "Zlarior", "what": "LIT · " + str(c.get("plan") or "MFFU Builder 50K"),
           "on": bool(hb.get("running")), "armed": bool(acc.get("armed")), "mode": acc.get("label") or ("PAPER" if hb.get("adapter") == "paper" else None),
           "stage": _t(str(st.get("label") or "") + (f" ({st['n']}/10)" if st.get("n") else ""), 50) or None,
           "wait": _t(st.get("waiting") or c.get("waiting"), 170) or None,
           "why": _lit_why(br) if br else None, "lv": _lit_levels(br), "arm": _lit_armed(br),
           "pos": _pos(c.get("position") or br.get("trade")), "day": _usd(_f(c.get("today_pnl"), _f(br.get("day_pnl")))),
           "room": _usd(c.get("room")), "mll": _usd(c.get("mll")), "log": _log(br.get("log")), "at": br.get("at"),
           "px": _f(br.get("price")), "chk": _lit_checks(br), "blk": [_t(x, 60) for x in _l(_d(br.get("guards")).get("blocking"))[:2]]}
    return out


def _lit_checks(br) -> list | None:
    """[passed, total] of the latest setup's checks (what the Brain's setup card shows; the engine has no A-D grade)."""
    for s in reversed(_l(br.get("setups"))):
        ch = [c for c in _l(_d(s).get("checks")) if isinstance(c, (list, tuple)) and len(c) >= 2]
        if ch:
            return [sum(1 for c in ch if c[1]), len(ch)]
    return None


def _price(hb) -> float | None:
    hb = _d(hb)
    return _f(_d(hb.get("brain")).get("price"), _f(hb.get("price")))


def _lobe(k) -> str | None:
    k = str(k or "")
    return next((x for x in ("ema", "macd", "sr") if k == x or k.startswith(x + "_")), None)


def _lobes(S, keys) -> list:
    """ATLAS's 3 lobes from second.compact's per-strategy state: [{id, st, text}] (st: window armed trade done off)."""
    out = []
    for k in keys:
        lid = _lobe(k)
        st = _d(_d(S.get(k)).get("state"))
        if lid and lid not in [x["id"] for x in out] and st:
            out.append({"id": lid, "st": LOBE_ST.get(str(st.get("stage")), "window"), "text": _t(st.get("text"), 70)})
    return out


def _sec_levels(S, keys, px=None) -> list:
    rows = []
    for k in keys:
        for x in _l(_d(_d(_d(S.get(k)).get("brain"))).get("levels"))[:4]:
            if isinstance(x, dict) and _f(x.get("px")) is not None and x.get("stage") not in ("taken", "used"):
                rows.append([_t(f"{_d(S.get(k)).get('short') or k} {x.get('name') or ''}", 28), round(_f(x["px"]), 2),
                             round(_f(x["px"]) - px, 1) if px is not None else None])
    return rows[:6]


def atlas(hb: dict, card: dict | None) -> dict:
    hb, c = _d(hb), _d(card)
    sec = _d(hb.get("second"))
    S = _d(sec.get("strategies"))
    ab = _d(_d(sec.get("route")).get("account_b"))
    members = [m for m in _l(c.get("members")) if isinstance(m, dict)]
    keys = [m.get("key") for m in members if m.get("key")] or [k for k, v in S.items() if _d(v).get("route")]
    arm, why, logs = [], [], []
    for k in keys:
        s = _d(S.get(k))
        b = _d(s.get("brain"))
        short = s.get("short") or k
        pl = _d(b.get("plan"))
        stg = _d(s.get("state")).get("stage")
        if pl and stg not in ("in_trade", "off"):
            arm.append({"side": str(pl.get("side") or "").upper(), "text": _t(f"{short}: entry {_px(pl.get('entry'))} · stop {_px(pl.get('stop'))} · "
                                                                            f"target {_px(pl.get('target'))}", 90),
                        "trig": _t(f"{short} enters {pl.get('when') or 'when its next check passes'}.", 150)})
        ff = b.get("first_fail")
        txt = _d(s.get("state")).get("text") or b.get("text")
        if txt:
            why.append(f"{short}: {txt}" + (f" (stopped by: {ff})" if ff and ff not in str(txt) else ""))
        for x in _l(b.get("log"))[-2:]:
            if isinstance(x, dict) and x.get("text"):
                tm = x.get("t")
                hm = time.strftime("%H:%M", time.localtime(int(tm))) if isinstance(tm, (int, float)) and tm > 0 else ""
                logs.append((tm or 0, [hm, _t(f"{short}: {x['text']}", 120)]))
    logs.sort(key=lambda z: -z[0])
    out = {"id": "atlas", "name": "ATLAS", "what": "EMA · MACD · S/R · " + str(c.get("plan") or "MFFU Builder 25K"),
           "on": bool(hb.get("running")) and bool(ab.get("enabled", bool(ab))), "armed": bool(ab.get("armed")),
           "mode": ab.get("label") or (str(ab.get("kind") or "").upper() or None),
           "wait": _t(c.get("waiting"), 170) or None, "why": _t(" · ".join(why), 220) or None,
           "lv": _sec_levels(S, keys, _price(hb)), "arm": arm[:2], "pos": _pos(c.get("position")), "day": _usd(c.get("today_pnl")),
           "room": _usd(c.get("room")), "mll": _usd(c.get("mll")), "log": [x[1] for x in logs[:4]],
           "px": _price(hb), "lobes": _lobes(S, keys), "dll": _usd(c.get("dll")), "dll_used": _dll_used(c)}
    return out


def _dll_used(c) -> int | None:
    """$ of the daily loss used today: the card's dll_used, else today's loss (0 on a green day)."""
    u = _f(_d(c).get("dll_used"))
    if u is None:
        d = _f(_d(c).get("today_pnl"))
        u = None if d is None else max(0.0, -d)
    return _usd(u)


def _atlas_log(hb, n) -> list:
    sec = _d(_d(hb).get("second"))
    S = _d(sec.get("strategies"))
    rows = []
    for k, s in S.items():
        s = _d(s)
        if not _d(s.get("brain")) or not (s.get("route") or _lobe(k)):
            continue
        for x in _l(_d(s.get("brain")).get("log")):
            if isinstance(x, dict) and x.get("text"):
                tm = x.get("t")
                hm = time.strftime("%H:%M", time.localtime(int(tm))) if isinstance(tm, (int, float)) and tm > 0 else ""
                rows.append((tm or 0, [hm, _t(f"{s.get('short') or k}: {x['text']}", 120)]))
    rows.sort(key=lambda z: -z[0])
    return [r[1] for r in rows[:n]]


def logs(hb: dict | None, n: int = LOG_N) -> dict | None:
    """The longer thought stream for the Brain page (pc_report ext block "glog"): the last n lines a bot, newest first. Never raises."""
    try:
        hb = _d(hb)
        out = {"lit": _log(_d(hb.get("brain")).get("log"), n), "atlas": _atlas_log(hb, n)}
        out = {k: v for k, v in out.items() if v}
        return out or None
    except Exception:  # noqa: BLE001
        return None


def cut_logs(g, n: int) -> None:
    """pc_report's cut for "glog": keep the newest n lines a bot."""
    if isinstance(g, dict):
        for k in list(g):
            if isinstance(g[k], list):
                g[k] = g[k][:n]


def rapid(hb: dict, rid: str = "rapid") -> dict | None:
    """The Rapid EOD 25K / 50K (engine/rapid.py): only when its lane (an extra account, lane / id "rapid") is configured;
    rid "rapid2" = the 2nd Rapid (data/rapid2.json, day-multirapid)."""
    hb = _d(hb)
    subs = _l(_d(hb.get("acct")).get("accounts"))
    hrow = next((r for r in _l(_d(hb.get("health")).get("accounts")) if isinstance(r, dict) and r.get("id") == rid), None)
    row = next((r for r in subs if isinstance(r, dict) and r.get("id") == rid), None)
    if not row and not hrow:
        return None
    row, hrow = _d(row), _d(hrow)
    pr = _d(row.get("plan_rules"))
    days = _d(_d(row.get("eval")).get("days"))
    prof = sum(_f(v, 0) or 0 for v in days.values()) if days else None
    floor = _f(_d(_d(row.get("eval")).get("anchor")).get("floor"))
    bal = (_f(pr.get("start")) or 0) + prof if prof is not None and pr.get("start") is not None else None
    room = (bal - floor) if bal is not None and floor is not None else None
    lk = row.get("locked") or hrow.get("locked")
    dis = _d(row.get("account")).get("disabled") or hrow.get("disabled")
    out = {"id": rid, "name": "Rapid EOD" + (" #2" if rid == "rapid2" else ""),
           "what": "LIT + ATLAS · MFFU Rapid EOD " + ("25K" if _f(pr.get("start")) == 25000.0 else "50K"),
           "on": bool(hrow.get("enabled", row.get("enabled"))) and bool(row.get("running", hb.get("running"))),
           "armed": bool(hrow.get("armed")), "mode": hrow.get("label") or _d(row.get("account")).get("label"),
           "wait": "Trades the same LIT setups as Zlarior (and ATLAS's when LIT is flat).",
           "why": _t(("Locked today: " + str(lk)) if lk else ("Off: " + str(dis)) if dis else "", 170) or None,
           "pos": _pos(row.get("position")), "day": _usd(_f(row.get("day_pnl"), hrow.get("day_pnl"))),
           "room": _usd(room), "mll": _usd(pr.get("mll")), "log": []}
    return out


def build(hb: dict | None, board: dict | None = None, now=None, max_bytes: int = MAX_BYTES) -> dict | None:
    """The glance of one heartbeat (+ the live board's cards). None when there is no heartbeat. Never raises."""
    try:
        hb = _d(hb)
        if not hb:
            return None
        bd = _d(board)
        bots = [lit(hb, bd.get("lit")), atlas(hb, bd.get("atlas"))]
        for rid in ("rapid", "rapid2"):
            r = rapid(hb, rid)
            if r:
                bots.append(r)
        out = {"v": VERSION, "t": int(_f(hb.get("t"), now or time.time())), "bots": [{k: v for k, v in b.items() if v not in (None, [], "")} for b in bots]}
        return fit(out, max_bytes)
    except Exception as e:  # noqa: BLE001
        return {"v": VERSION, "error": f"{e.__class__.__name__}: {_t(e, 100)}"}


def size(o) -> int:
    return len(json.dumps(o, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8"))


def fit(g: dict, max_bytes: int = MAX_BYTES) -> dict:
    """Cut the least needed parts first: log lines, then levels, then the trigger texts, until it fits."""
    steps = [("log", 2), ("lv", 4), ("log", 1), ("lv", 2), ("arm", 1), ("blk", 1), ("log", 0), ("lv", 0), ("blk", 0)]
    for key, n in steps:
        if size(g) <= max_bytes:
            break
        for b in g.get("bots") or []:
            if isinstance(b.get(key), list):
                b[key] = b[key][:n]
        g["trimmed"] = True
    if size(g) > max_bytes:
        for b in g.get("bots") or []:
            for k in ("why", "wait"):
                if isinstance(b.get(k), str):
                    b[k] = _t(b[k], 80)
    if size(g) > max_bytes:              # the essentials only: on / armed, $ today, room, the open trade's $, what it waits for
        for b in g.get("bots") or []:
            b.pop("what", None)
            b.pop("why", None)
            for k in ("lobes", "chk", "blk", "lv", "arm"):
                b.pop(k, None)
            if isinstance(b.get("pos"), dict):
                b["pos"] = {k: v for k, v in b["pos"].items() if k in ("side", "qty", "risk_usd", "tgt_usd", "now_usd")}
    return g


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argv[0] if argv else None
    if not p:
        print("usage: python -X utf8 -m engine.brain_glance <heartbeat.json>")
        return 2
    with open(p, encoding="utf-8") as fh:
        hb = json.load(fh)
    board = None
    try:
        from engine import live_board
        board = live_board.from_heartbeat(hb)
    except Exception:  # noqa: BLE001
        board = None
    print(json.dumps(build(hb, board), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
