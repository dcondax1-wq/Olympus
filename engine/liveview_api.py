"""Read-only API of the Live View page (web_next/js/next/liveview.js; owner 2026-10-28: "a very big screen I can full
screen with a WHITE background for the live chart and mock-ups of what's happening; each strategy a different color ...
a switch where I can see exactly what the bots are thinking").

  GET /api/next/liveview?tf=1m|5m     one answer per refresh (~3 s): the bot's own bars of today's session (NinjaTrader feed;
                                      before the bot has bars: the last session of data/NQ_<tf>.csv, the TradingView CME
                                      export), and one layer per strategy:
                                        lit    Zlarior: today's LIT levels (swept / untouched), the setup forming (sweep extreme,
                                               swept level, CISD level), the armed limit / stop / target, today's setups, the
                                               live position with its REAL micros and $ (routed leg), the thinking panel
                                               (stage, plain sentence, checklist, distance to the trigger, window countdown)
                                        atlas  ATLAS: EMA 21 / 50 on 5m, each member's stage + checks (MACD sweep state, S/R
                                               levels), paper plans (no size), the REAL account B / routed position
                                        scalp  Strategy 3 = BLITZ, the scalper PAPER shadow (engine/blitz.py, LiveBot.blitz):
                                               today's noise band (next check's lines + every check as "band"), its signals,
                                               the paper position and trades (simulated 25K eval micros, labelled PAPER);
                                               also any second_model.json member whose key starts with "scalp"; a placeholder
                                               before either runs
                                      + the narrator's feed (engine/narrator.py, last 100 messages)
  GET /api/next/liveview/feed?after=  just the feed (newest first), for the ticker
  phone_view()                        liveview.json for the phone (same layers; 1m + 5m bars), pushed by engine/live_publish

Only READS the bot (engine/live.BOT: brain, state, ledger, health, bars_tail, the 1m store, second, acct_b, adapter legs via
engine/accounts._position). Nothing here starts, arms, routes, sizes or changes anything; no answer carries a confirm
phrase, webhook URL or file path. Mounted by server.py with one include line.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time

from fastapi import APIRouter
from fastapi.responses import Response

from . import narrator as N

router = APIRouter()
PV = 2.0
COLORS = {"lit": "#2563eb", "atlas": "#ea580c", "scalp": "#7c3aed"}
CSV_FALLBACK = True            # tests switch it off (no real data/ files)
_WIN = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    """The PC bot (tests replace this function)."""
    from .live import BOT
    return BOT


def _now(bot) -> int:
    try:
        return int(bot.clock())
    except Exception:
        return int(time.time())


def _f(v, d=2):
    try:
        x = float(v)
        return None if x != x else round(x, d)
    except (TypeError, ValueError):
        return None


def session_bounds(now: int):
    day = N.trading_day(now)
    d = dt.date.fromisoformat(day)
    p = d - dt.timedelta(days=1)
    t0 = int(dt.datetime(p.year, p.month, p.day, 18, 0, tzinfo=N.ET).timestamp())
    t1 = int(dt.datetime(d.year, d.month, d.day, 17, 0, tzinfo=N.ET).timestamp())
    return t0, t1, day


# ---------------------------------------------------------------------------------------------- bars
def bars(bot, tf: str, now: int) -> dict:
    """{"bars", "hist5", "source", "day", "t0", "t1"}: today's session from the bot's own feed; hist5 = 5m bars from 2 days
    back (EMA warm-up). Without the bot's bars, the last session of data/NQ_<tf>.csv."""
    from . import pcdash_api
    t0, t1, day = session_bounds(now)
    b5h, b1 = pcdash_api.bot_bars(bot, t0 - 2 * 86400)
    b5 = [b for b in b5h if b[0] >= t0]
    b1 = [b for b in b1 if b[0] >= t0]
    rows, src = (b1 if tf == "1m" else b5), "the bot's NinjaTrader feed"
    if not rows and CSV_FALLBACK:
        df = pcdash_api._csv("NQ", tf)
        if df is not None and len(df):
            last = int(df["time"].iloc[-1])
            t0, t1, day = session_bounds(min(now, last))
            rows = pcdash_api._rows_from_frame(df[(df["time"] >= t0) & (df["time"] <= t1)])
            src = f"data/NQ_{tf}.csv (last session {day}: the bot has no bars yet)"
            d5 = pcdash_api._csv("NQ", "5m")
            if d5 is not None and len(d5):
                b5h = pcdash_api._rows_from_frame(d5[(d5["time"] >= t0 - 2 * 86400) & (d5["time"] <= t1)])
    rows = rows[-(900 if tf == "1m" else 300):]
    return {"bars": rows, "hist5": b5h, "source": src, "day": day, "t0": t0, "t1": t1}


def ema(rows, n: int, t_from: int | None = None) -> list:
    """[[t, ema]] of the closes (a plain EMA, alpha 2/(n+1), seeded with the first close)."""
    out, e, a = [], None, 2.0 / (n + 1)
    for r in rows:
        c = float(r[4])
        e = c if e is None else e + a * (c - e)
        if t_from is None or r[0] >= t_from:
            out.append([int(r[0]), round(e, 2)])
    return out


# ---------------------------------------------------------------------------------------------- windows
def windows_of(text) -> list:
    """"02:00-05:00, 09:30-11:00 ET" -> [(120, 300), (570, 660)] (ET minutes)."""
    return [(int(a) * 60 + int(b), int(c) * 60 + int(d)) for a, b, c, d in _WIN.findall(str(text or ""))]


def window_state(now: int, wins) -> dict | None:
    """Open now (until when) or the next opening (weekdays), seconds to it."""
    if not wins:
        return None
    e = N._et(now)
    mod = e.hour * 60 + e.minute
    if e.weekday() < 5:
        for a, z in wins:
            if a <= mod < z:
                end = e.replace(hour=z // 60, minute=z % 60, second=0, microsecond=0)
                return {"open": True, "label": f"window open until {z // 60:02d}:{z % 60:02d} ET", "t": int(end.timestamp()),
                        "secs": int(end.timestamp()) - now}
    for k in range(0, 8):
        d = e.date() + dt.timedelta(days=k)
        if d.weekday() >= 5:
            continue
        for a, _z in sorted(wins):
            st = dt.datetime(d.year, d.month, d.day, a // 60, a % 60, tzinfo=N.ET)
            if st.timestamp() > now:
                return {"open": False, "label": f"next window {st:%a} {a // 60:02d}:{a % 60:02d} ET", "t": int(st.timestamp()),
                        "secs": int(st.timestamp()) - now}
    return None


# ---------------------------------------------------------------------------------------------- Zlarior (LIT)
ORDER = {"sweep": 1, "inducement": 2, "displacement": 3, "cisd5": 4}


def lead_watch(brain) -> dict | None:
    """The side whose setup is furthest along (it swept something), else None."""
    ws = [w for w in (brain or {}).get("watch") or [] if isinstance(w, dict) and w.get("swept")]
    if not ws:
        return None
    return max(ws, key=lambda w: (ORDER.get(w.get("stage"), 0), w.get("ext_t") or 0))


def lit_thinking(brain: dict | None, pos: dict | None, price, now: int, rules: dict | None = None) -> dict:
    """The thinking panel: stage, one plain sentence (e.g. "Swept London high 29,987 · waiting for a 5m displacement >= 0.8
    ATR · then a CISD close below 29,945"), the checklist (ticks / crosses), distance to the trigger, the window countdown."""
    b = brain or {}
    rules = rules or b.get("rules") or {}
    st = b.get("stage") or {}
    win = N.lit_window(now)
    out = {"stage": {k: st.get(k) for k in ("key", "label", "n", "waiting")}, "stages": b.get("stages") or [], "window": win,
           "checklist": [], "distance": None, "headline": st.get("waiting") or "", "detail": None}
    if not b:
        out["headline"] = "The Bot Brain has nothing yet: it fills after the bot's first poll while the bot runs."
        return out
    dmin, need_disp = rules.get("depth", 0.5), rules.get("disp", 0.8)
    key = st.get("key")
    armed = next((s for s in reversed(b.get("setups") or []) if isinstance(s, dict) and s.get("status") in ("armed", "tapped")), None)
    w = lead_watch(b)
    if key == "trade" and (pos or b.get("trade")):
        tr = b.get("trade") or {}
        p = pos or {}
        d = int(p.get("dir") or tr.get("dir") or 1)
        q = p.get("qty")
        entry, stop, tgt = p.get("entry") or tr.get("entry"), p.get("stop") or tr.get("stop"), p.get("target") or tr.get("target")
        be = (tr.get("be") or {})
        parts = [f"In a {N.side_word(d)}" + (f" {q} MNQ" if q and not p.get("paper") else " (model, not routed)") + f" from {N.px(entry)}"]
        if be and not be.get("done") and be.get("trigger") is not None:
            parts.append(f"waiting for +1R at {N.px(be['trigger'])} to move the stop to breakeven")
        elif be.get("done"):
            parts.append("stop at breakeven: this trade can't lose")
        parts.append(f"stop {N.px(stop)} · target {N.px(tgt)} · flat 15:55")
        out["headline"] = " · ".join(parts)
        if price is not None and entry is not None:
            dist = []
            if stop is not None:
                dist.append({"label": "to the stop", "pts": round(abs(float(price) - float(stop)), 2)})
            if tgt is not None:
                dist.append({"label": "to the target", "pts": round(abs(float(tgt) - float(price)), 2)})
            if be and be.get("trigger") is not None and not be.get("done"):
                dist.append({"label": "to breakeven (+1R)", "pts": round(abs(float(be["trigger"]) - float(price)), 2)})
            out["distance"] = dist
        tc = tr.get("t_check") or {}
        out["checklist"] = [{"label": "Breakeven at +1R", "ok": True if be.get("done") else None, "text": be.get("text")},
                            {"label": "15-minute check", "ok": {"passed": True, "cut": False}.get(tc.get("state")), "text": tc.get("text")},
                            {"label": "Target", "ok": None, "text": f"{N.px(tgt)} ({tr.get('target_label') or 'VIX band'})"},
                            {"label": "Flat 15:55", "ok": None, "text": (tr.get("flat") or {}).get("text") or "Flat at 15:55 ET if still open"}]
        return out
    if armed or key in ("limit", "cisd1m"):
        s = armed or {}
        plan = s.get("plan") or {}
        out["checklist"] = [{"label": c.get("label"), "ok": c.get("ok"), "text": c.get("text")} for c in s.get("checks") or []]
        if price is not None and plan.get("limit") is not None:
            out["distance"] = [{"label": "to the limit", "pts": round(abs(float(price) - float(plan["limit"])), 2)}]
        if plan.get("expires_t"):
            out["expires"] = {"t": int(plan["expires_t"]), "secs": int(plan["expires_t"]) - now}
        out["detail"] = s.get("status_text")
        return out
    if w:
        d = int(w.get("dir") or 1)
        word = "below" if d < 0 else "above"
        parts = [f"Swept {', '.join(w.get('swept')[:2])}" + (f" +{len(w['swept']) - 2} more" if len(w.get('swept') or []) > 2 else "")
                 + (f" {N.px(w.get('level'))}" if w.get("level") is not None else "")]
        if w.get("depth_ok") is False:
            parts.append(f"needs a deeper sweep (>= {dmin} ATR; {float(w.get('depth_atr') or 0):.2f} so far)")
        if w.get("idm_ok") is False:
            parts.append("no inducement swing was taken first")
        atr = _f(w.get("atr")) or 0
        if not w.get("disp_ok"):
            parts.append(f"waiting for a 5m displacement >= {need_disp} ATR ({need_disp * atr:.1f} pts; best {float(w.get('disp') or 0):.2f})")
        if w.get("cisd") is not None and not w.get("cisd_closed"):
            parts.append(f"then a CISD close {word} {N.px(w['cisd'])}")
        out["headline"] = " · ".join(parts)
        out["detail"] = w.get("text")
        out["checklist"] = [
            {"label": f"Sweep depth >= {dmin} ATR", "ok": w.get("depth_ok"),
             "text": f"{float(w.get('depth_atr') or 0):.2f} ATR = {float(w.get('depth_pts') or 0):.1f} pts beyond {N.px(w.get('level'))}"},
            {"label": "Inducement taken first", "ok": w.get("idm_ok"), "text": f"{w.get('idm_n') or 0} swing(s) taken before the sweep"},
            {"label": f"Displacement >= {need_disp} ATR", "ok": True if w.get("disp_ok") else None,
             "text": f"best body {float(w.get('disp') or 0):.2f} ATR (needs {need_disp} = {need_disp * atr:.1f} pts)"},
            {"label": f"5m CISD close {word} {N.px(w.get('cisd'))}", "ok": True if w.get("cisd_closed") else None,
             "text": f"{abs(float(w.get('cisd_dist') or 0)):.1f} pts away" if w.get("cisd") is not None else "no CISD level yet"},
            {"label": "Entry window 02:00-15:30 ET", "ok": bool(win.get("open")), "text": win.get("label")},
            {"label": "1 trade a day", "ok": not int(b.get("day_trades") or 0), "text": "free" if not int(b.get("day_trades") or 0) else "a trade already done today"},
        ]
        if w.get("cisd_dist") is not None and not w.get("cisd_closed"):
            out["distance"] = [{"label": "to the CISD close", "pts": round(abs(float(w["cisd_dist"])), 2)}]
        stop_prev = _f(w.get("stop_preview"))
        if stop_prev:
            out["stop_preview"] = stop_prev
    else:
        nb = b.get("nearest") or {}
        up, dn = (nb.get("above") or [None])[0], (nb.get("below") or [None])[0]
        bits = ["Watching today's levels for a sweep"]
        if up:
            bits.append(f"nearest above {up.get('label')} {N.px(up.get('price'))} ({abs(float(up.get('dist') or 0)):.1f} pts)")
        if dn:
            bits.append(f"below {dn.get('label')} {N.px(dn.get('price'))} ({abs(float(dn.get('dist') or 0)):.1f} pts)")
        if key == "done":
            bits = [st.get("waiting") or "Done for today"]
        out["headline"] = " · ".join(bits)
        out["distance"] = [x for x in ([{"label": f"to {up.get('label')}", "pts": round(abs(float(up.get("dist") or 0)), 2)}] if up else [])
                           + ([{"label": f"to {dn.get('label')}", "pts": round(abs(float(dn.get("dist") or 0)), 2)}] if dn else [])]
        out["checklist"] = [{"label": "Entry window 02:00-15:30 ET", "ok": bool(win.get("open")), "text": win.get("label")},
                            {"label": "1 trade a day", "ok": not int(b.get("day_trades") or 0),
                             "text": "free" if not int(b.get("day_trades") or 0) else "a trade already done today"}]
    g = b.get("guards") or {}
    if g.get("blocking"):
        out["checklist"].append({"label": "Guards", "ok": False, "text": ", ".join(str(x.get("label") if isinstance(x, dict) else x) for x in g["blocking"])[:200]})
    return out


def lit_layer(bot, now: int, price) -> dict:
    from . import accounts
    b = getattr(bot, "brain", None) or {}
    pos = None
    try:
        p = accounts._position(bot)
        if p and not getattr(bot, "_open_src", None) and p.get("entry") is not None:
            from .pcdash_api import _position_view
            pos = _position_view(bot, p, now)
    except Exception:
        pos = None
    if pos is None and isinstance(b.get("trade"), dict):          # the model's trade, not routed on an account: no size
        tr = b["trade"]
        pos = {"side": tr.get("side"), "dir": tr.get("dir"), "entry": tr.get("entry"), "stop": tr.get("stop"), "stop0": tr.get("stop0"),
               "target": tr.get("target"), "entry_t": tr.get("entry_t"), "paper": True, "be_trigger": (tr.get("be") or {}).get("trigger")}
    lines, levels, marks = [], [], []
    for lv in b.get("levels") or []:
        if isinstance(lv, dict) and lv.get("price") is not None:
            levels.append({"label": lv.get("label"), "price": _f(lv.get("price")), "side": lv.get("side"), "kind": lv.get("kind"),
                           "taken": bool(lv.get("taken")), "taken_t": lv.get("taken_t"), "taken_hm": lv.get("taken_hm"),
                           "deep_ok": lv.get("deep_ok"), "depth_atr": lv.get("depth_atr")})
    setup = None
    w = lead_watch(b)
    if w and b.get("stage", {}).get("key") not in ("trade", "done"):
        setup = {"dir": w.get("dir"), "side": w.get("side"), "stage": w.get("stage"), "swept": w.get("swept"), "level": _f(w.get("level")),
                 "ext": _f(w.get("ext")), "ext_t": w.get("ext_t"), "cisd": _f(w.get("cisd")), "cisd_closed": w.get("cisd_closed"),
                 "disp_ok": w.get("disp_ok"), "idm_ok": w.get("idm_ok"), "depth_ok": w.get("depth_ok")}
    armed = next((s for s in reversed(b.get("setups") or []) if isinstance(s, dict) and s.get("status") in ("armed", "tapped")), None)
    if armed and armed.get("plan"):
        pl = armed["plan"]
        lines += [{"id": "limit", "label": f"Limit {armed.get('side')} {N.px(pl.get('limit'))} · until {pl.get('expires_hm') or ''}",
                   "price": _f(pl.get("limit")), "style": "solid", "t0": pl.get("armed_t"), "t1": pl.get("expires_t")},
                  {"id": "plan_stop", "label": f"Stop {N.px(pl.get('stop'))} ({float(pl.get('stop_pts') or 0):.1f} pts)", "price": _f(pl.get("stop")),
                   "style": "dash", "t0": pl.get("armed_t")},
                  {"id": "plan_target", "label": f"Target {N.px(pl.get('target'))} ({pl.get('target_label') or 'VIX band'}, {float(pl.get('rr') or 0):.1f}R)",
                   "price": _f(pl.get("target")), "style": "dash", "t0": pl.get("armed_t")}]
        setup = {**(setup or {}), "armed": {"limit": _f(pl.get("limit")), "stop": _f(pl.get("stop")), "target": _f(pl.get("target")),
                                            "armed_t": pl.get("armed_t"), "expires_t": pl.get("expires_t"), "side": armed.get("side"),
                                            "ext": _f(armed.get("ext")), "cisd": _f(armed.get("cisd")), "t": armed.get("t"),
                                            "status": armed.get("status")}}
    if pos:
        real = not pos.get("paper")
        q = pos.get("qty") if real else None
        d = int(pos.get("dir") or (1 if pos.get("side") == "LONG" else -1))
        entry, stop, tgt = _f(pos.get("entry")), _f(pos.get("stop")), _f(pos.get("target"))
        usd_at = (lambda p_: round((float(p_) - float(entry)) * d * PV * float(q), 0)) if (real and q and entry is not None) else (lambda p_: None)
        lines.append({"id": "entry", "label": f"Entry {pos.get('side') or N.side_word(d)} " + (f"{q} MNQ" if real else "(model, not routed: no size)")
                      + f" @ {N.px(entry)}", "price": entry, "style": "solid", "t0": pos.get("entry_t"), "strong": True})
        if stop is not None:
            u = usd_at(stop)
            lines.append({"id": "stop", "label": f"Stop {N.px(stop)}" + (f" · {N.usd(u)}" if u is not None else ""), "price": stop, "style": "solid",
                          "t0": pos.get("entry_t"), "strong": True, "tone": "bad" if u is None or u < 0 else "good"})
        if tgt is not None:
            u = usd_at(tgt)
            lines.append({"id": "target", "label": f"Target {N.px(tgt)}" + (f" · {N.usd(u)}" if u is not None else ""), "price": tgt, "style": "solid",
                          "t0": pos.get("entry_t"), "strong": True, "tone": "good"})
        if pos.get("be_trigger") is not None and stop is not None and entry is not None and (stop - entry) * d < 0:
            lines.append({"id": "be", "label": f"BE trigger +1R {N.px(pos['be_trigger'])}", "price": _f(pos["be_trigger"]), "style": "dot",
                          "t0": pos.get("entry_t")})
        pos = {k: pos.get(k) for k in ("side", "dir", "qty", "entry", "stop", "stop0", "target", "entry_t", "price", "unrealized_usd",
                                        "unrealized_r_now", "risk_usd", "target_usd", "be", "paper", "broker", "target_label")}
        if not real:
            pos["qty"] = None
    for s in b.get("setups") or []:
        if isinstance(s, dict) and s.get("t"):
            marks.append({"t": int(s["t"]), "price": _f(s.get("cisd")), "kind": "setup", "status": s.get("status"), "side": s.get("side"),
                          "text": s.get("status_text") or s.get("status")})
    for r in list(getattr(bot, "ledger", None) or []):
        if not isinstance(r, dict) or r.get("src") or not r.get("t") or N.trading_day(int(r["t"])) != N.trading_day(now):
            continue
        if r.get("side") in ("buy", "sell", "exit"):
            res = r.get("result") or {}
            fill = next((x.get("fill_px") for x in (res.get("legs") or []) if isinstance(x, dict) and x.get("fill_px") is not None), None)
            marks.append({"t": int(r["t"]), "kind": "entry" if r["side"] != "exit" else "exit", "side": r["side"], "qty": r.get("qty"),
                          "price": _f(fill or r.get("entry") or r.get("exit_px") or r.get("price")), "pnl": _f(r.get("pnl")),
                          "ok": res.get("ok", True), "text": r.get("reason")})
    return {"key": "lit", "name": "Zlarior", "sub": "LIT method", "color": COLORS["lit"], "levels": levels, "setup": setup, "lines": lines,
            "marks": marks, "position": pos, "thinking": lit_thinking(b, pos, price, now), "brain_at": b.get("at"),
            "model_state": b.get("model_state"), "atr": b.get("atr")}


# ---------------------------------------------------------------------------------------------- ATLAS + Strategy 3
def _member(k, s, now) -> dict:
    st = s.get("state") or {}
    br = s.get("brain") or {}
    plan = br.get("plan") if isinstance(br.get("plan"), dict) else None
    lv = [{"name": x.get("name"), "price": _f(x.get("px")), "stage": x.get("stage")} for x in (br.get("levels") or [])
          if isinstance(x, dict) and x.get("px") is not None][:14]
    return {"key": k, "short": s.get("short") or k, "label": s.get("label") or k, "stage": st.get("stage"), "text": st.get("text"),
            "window": window_state(now, windows_of(st.get("window"))), "window_text": st.get("window"),
            "checks": [{"label": c.get("name"), "ok": c.get("ok"), "text": c.get("val") or c.get("need")} for c in (br.get("checks") or [])],
            "first_fail": br.get("first_fail"), "plan": plan, "levels": lv, "route": bool(s.get("route")),
            "trend": st.get("trend"), "ema50_5m": _f(st.get("ema50_5m")), "error": s.get("error"), "candidate": bool(s.get("candidate"))}


def atlas_layer(bot, now: int, hist5, t0: int, price) -> dict:
    sec = getattr(bot, "second", None) or {}
    members, scalp = [], []
    for k, s in (sec.get("strategies") or {}).items():
        if not isinstance(s, dict) or s.get("on") is False:
            continue
        m = _member(k, s, now)
        if str(k).startswith("lit"):                           # Zlarior's own paper variants (the Asia slot): not ATLAS
            m["candidate"], m["other"] = True, True
        (scalp if str(k).startswith("scalp") else members).append(m)
    lines, levels = [], []
    for m in members:
        if m.get("candidate"):
            continue                                           # stop-hunt candidates: listed in the panel, not drawn
        for x in m["levels"]:
            levels.append({"label": f"{m['short']} {x['name'] or 'S/R'}", "price": x["price"], "stage": x.get("stage")})
        pl = m.get("plan") or {}
        if pl.get("entry") is not None and m.get("stage") not in ("off", "done"):
            lines.append({"id": f"{m['key']}_plan", "label": f"{m['short']} plan {str(pl.get('side') or '').upper()} {N.px(pl.get('entry'))} (paper, no size)",
                          "price": _f(pl.get("entry")), "style": "dash"})
            if pl.get("stop") is not None:
                lines.append({"id": f"{m['key']}_pstop", "label": f"{m['short']} stop {N.px(pl.get('stop'))}", "price": _f(pl.get("stop")), "style": "dot"})
    pos, account, marks = None, None, []
    ab = getattr(bot, "acct_b", None)
    if ab is not None:
        try:
            info = ab.info(now)
            account = info.get("label")
            op = info.get("open")
            if op and op.get("entry") is not None:
                pos = {**op, "account": account}
            for r in info.get("routed") or []:
                if r.get("t") and N.trading_day(int(r["t"])) == N.trading_day(now) and r.get("side") in ("buy", "sell", "exit"):
                    marks.append({"t": int(r["t"]), "kind": "entry" if r["side"] != "exit" else "exit", "side": r["side"], "qty": r.get("qty"),
                                  "price": None, "pnl": _f(r.get("pnl")), "ok": r.get("ok", True), "text": r.get("strategy")})
        except Exception:
            pass
    if pos is None and callable(getattr(bot, "_second_pos", None)):
        try:
            op = bot._second_pos()
            if op and op.get("entry") is not None:
                pos = {**op, "side": N.side_word(op.get("dir")), "account": bot._push_account(), "strategy": op.get("setup")}
        except Exception:
            pass
    if pos:
        d = int(pos.get("dir") or 1)
        q = pos.get("qty")
        entry = _f(pos.get("entry"))

        def u(p_):
            return round((float(p_) - float(entry)) * d * PV * float(q), 0) if (q and entry is not None and p_ is not None) else None
        lines.append({"id": "b_entry", "label": f"ATLAS {pos.get('strategy') or ''} {N.side_word(d)} {q} MNQ @ {N.px(entry)} ({pos.get('account')})",
                      "price": entry, "style": "solid", "strong": True, "t0": pos.get("entry_t")})
        for kk, nm in (("stop", "stop"), ("target", "target")):
            if pos.get(kk) is not None:
                lines.append({"id": f"b_{kk}", "label": f"ATLAS {nm} {N.px(pos[kk])} · {N.usd(u(pos[kk]))}", "price": _f(pos[kk]), "style": "solid",
                              "strong": True, "t0": pos.get("entry_t")})
        if price is not None and entry is not None and q:
            pos["unrealized_usd"] = round((float(price) - entry) * d * PV * float(q), 2)
    e21 = ema(hist5, 21, t0)
    e50 = ema(hist5, 50, t0)
    return {"atlas": {"key": "atlas", "name": "ATLAS", "sub": "EMA · MACD · S/R", "color": COLORS["atlas"], "members": members,
                      "ema21": e21, "ema50": e50, "levels": levels, "lines": lines, "marks": marks, "position": pos, "account": account,
                      "empty": None if sec else "ATLAS has not run yet: it runs after each Zlarior poll while the bot runs."},
            "scalp": {"key": "scalp", "name": "Strategy 3 (research)", "sub": "scalp bot", "color": COLORS["scalp"], "placeholder": not scalp,
                      "members": scalp, "lines": [], "marks": [], "signals": [],
                      "text": None if scalp else "The scalp bot is still in research (research/scalp). Its signals show on this layer once it "
                                                 "runs as a paper strategy; nothing is traded."}}


# ---------------------------------------------------------------------------------------------- BLITZ (strategy 3, PAPER)
def blitz_layer(bot, now: int, price) -> dict | None:
    """The purple layer from the BLITZ scalper PAPER shadow (engine/blitz.py, LiveBot.blitz): today's noise band (09:30 open
    +/- sigma at each check; the next check's lines), its signals, and both paper ledgers labelled PAPER: the simulated 25K
    eval and the funded 50K next to LIT (only while LIT is flat). None when BLITZ has not run. Never routed: nothing here has
    a real size."""
    S = getattr(bot, "blitz", None)
    if not isinstance(S, dict) or not (S.get("eng") or S.get("error")):
        return None
    from . import blitz as BZ
    if not S.get("eng"):
        return {"error": str(S.get("error"))[:200], "members": [{"key": "blitz", "short": "BLITZ", "stage": "error", "text": str(S.get("error"))[:200]}]}
    c = BZ.compact(S, n=40)
    f50 = c.get("funded50") or {}
    day = BZ.et_date(now)
    st = c.get("state") or {}
    lines, marks, signals, band = [], [], [], None
    b = c.get("band") or {}
    if b.get("o0") is not None and b.get("date") == day:
        rows = [r for r in b.get("checks") or [] if r.get("up") is not None]
        band = [[int(r["t"]), r["up"], r["lo"]] for r in rows]
        nxt = next((r for r in rows if int(r["t"]) > now), rows[-1] if rows else None)
        off = "" if b.get("day_ok", True) else " (day filter: no trades today)"
        if nxt:
            lines += [{"id": "blz_up", "label": f"BLITZ band {N.px(nxt['up'])} · {nxt['hm']} close above = PAPER LONG{off}", "price": _f(nxt["up"]),
                       "style": "dash"},
                      {"id": "blz_lo", "label": f"BLITZ band {N.px(nxt['lo'])} · {nxt['hm']} close below = PAPER SHORT{off}", "price": _f(nxt["lo"]),
                       "style": "dash"}]
        lines.append({"id": "blz_o0", "label": f"BLITZ 09:30 open {N.px(b['o0'])}", "price": _f(b["o0"]), "style": "dot"})
    for x in c.get("signals") or []:
        side = N.side_word(x.get("dir"))
        txt = (f"PAPER signal {side}: close {N.px(x.get('close'))} beyond the band {N.px(x.get('band'))}"
               + ("" if x.get("taken") else f" · not taken ({x.get('why')})"))
        signals.append({"t": int(x["t"]), "close_t": x.get("close_t"), "side": side, "dir": x.get("dir"), "price": _f(x.get("close")),
                        "band": _f(x.get("band")), "taken": bool(x.get("taken")), "text": txt})
        marks.append({"t": int(x["t"]), "kind": "signal", "side": side, "price": _f(x.get("close")), "status": "taken" if x.get("taken") else "skipped",
                      "text": txt})
    for x in f50.get("skipped") or []:
        signals.append({"t": int(x["t"]), "close_t": x.get("close_t"), "side": N.side_word(x.get("dir")), "dir": x.get("dir"),
                        "price": _f(x.get("close")), "taken": False, "ledger": "50k", "text": f"PAPER 50K: not taken ({x.get('why')})"})
    for tag, rows_ in (("25K eval", c.get("today") or []), ("50K + LIT", f50.get("today") or [])):
        for r in rows_:
            q = int(r.get("qty") or 0)
            if r.get("exit_kind") == "SKIP":
                continue
            marks.append({"t": int(r["entry_t"]), "kind": "entry", "side": "buy" if int(r["dir"]) > 0 else "sell", "qty": q or None,
                          "price": _f(r.get("entry")), "paper": True, "ledger": tag,
                          "text": f"PAPER {tag}" + ("" if q else f" (no size: {r.get('skip')})")})
            if r.get("exit_t") and r.get("exit_kind") not in (None, "OPEN"):
                marks.append({"t": int(r["exit_t"]) - 60, "kind": "exit", "side": r.get("side"), "qty": q or None, "price": _f(r.get("exit")),
                              "pnl": _f(r.get("usd")), "paper": True, "ledger": tag, "text": f"PAPER {tag} {str(r['exit_kind']).upper()}"})

    def pos_of(op, tag):
        if not op or op.get("entry") is None or op.get("exit_kind") != "OPEN":
            return None
        d = int(op.get("dir") or 1)
        q = int(op.get("qty") or 0)
        entry, stop = _f(op.get("entry")), _f(op.get("stop_now") or op.get("stop"))
        u = (lambda p_: round((float(p_) - entry) * d * PV * q, 0) if (q and p_ is not None) else None)
        return {"side": N.side_word(d), "dir": d, "qty": q or None, "entry": entry, "stop": stop, "stop0": _f(op.get("stop")), "target": None,
                "entry_t": op.get("entry_t"), "time_exit_t": op.get("time_exit_t"), "paper": True, "best": _f(op.get("best")), "ledger": tag,
                "unrealized_usd": u(price) if price is not None else None, "stop_usd": u(stop) if stop is not None else None,
                "label": f"PAPER ({'simulated 25K eval' if tag == '25K eval' else 'simulated funded 50K next to LIT'} micros, never routed)"}
    pos, pos50 = pos_of(c.get("open"), "25K eval"), pos_of(f50.get("open"), "50K + LIT")
    same = pos and pos50 and pos["entry_t"] == pos50["entry_t"]
    for P_, pre in ((pos, "blz"), (None if same else pos50, "b50")):
        if not P_:
            continue
        sizes = (f"25K eval {P_['qty'] or 0} MNQ · 50K {pos50['qty'] or 0} MNQ" if same else
                 f"{P_['ledger']} {P_['qty']} MNQ" if P_["qty"] else f"{P_['ledger']} no size")
        lines += [{"id": f"{pre}_entry", "label": f"BLITZ PAPER {P_['side']} @ {N.px(P_['entry'])} · {sizes}", "price": P_["entry"],
                   "style": "solid", "strong": True, "t0": P_["entry_t"], "paper": True},
                  {"id": f"{pre}_stop", "label": f"BLITZ PAPER stop {N.px(P_['stop'])}" + (f" · {N.usd(P_['stop_usd'])} paper" if P_["stop_usd"] is not None else ""),
                   "price": P_["stop"], "style": "solid", "strong": True, "t0": P_["entry_t"], "paper": True,
                   "tone": "good" if P_["stop_usd"] is not None and P_["stop_usd"] >= 0 else "bad"}]
        if P_["stop"] is not None and P_["stop0"] is not None and P_["stop"] == P_["stop0"]:
            one_r = P_["entry"] + P_["dir"] * abs(P_["entry"] - P_["stop0"])
            lines.append({"id": f"{pre}_trail", "label": f"BLITZ trail starts +1R {N.px(one_r)}", "price": _f(one_r), "style": "dot",
                          "t0": P_["entry_t"], "paper": True})
    ev, m = c.get("eval") or {}, c.get("money") or {}
    a5, m5 = f50.get("account") or {}, f50.get("money") or {}
    ev_txt = (f"Paper 25K eval {ev.get('n')}: session {ev.get('session')}, balance ${float(ev.get('balance') or 0):,.0f}, "
              f"room ${float(ev.get('room') or 0):,.0f}, ${float(ev.get('to_target') or 0):,.0f} to pass · {m.get('n', 0)} paper trades, "
              f"${float(m.get('usd') or 0):+,.0f}") if ev.get("n") else ""
    f_txt = (f"Paper funded 50K next to LIT {a5.get('n')}: balance ${float(a5.get('balance') or 0):,.0f}, today "
             f"${float(a5.get('today') or 0):+,.0f} · {m5.get('sized', 0)} trades, ${float(m5.get('usd') or 0):+,.0f}, "
             f"{m5.get('skipped', 0)} skipped (ATLAS), {m5.get('masked', 0)} signals while LIT was busy") if a5.get("n") else ""
    op50 = f50.get("open")
    f_state = (f"PAPER {N.side_word(op50.get('dir'))} {op50.get('qty') or 0} MNQ from {N.px(op50.get('entry'))}" if op50 and op50.get("exit_kind") == "OPEN"
               else "flat; trades only while LIT is flat (no LIT trade, no LIT setup armed)")
    return {"name": "BLITZ", "sub": "scalper · PAPER shadow", "label": BZ.LABEL, "paper": True, "never_routed": True,
            "members": [{"key": "blitz", "short": "BLITZ", "label": BZ.LABEL, "stage": st.get("stage"), "text": st.get("text"), "paper": True},
                        {"key": "blitz50", "short": "BLITZ 50K + LIT", "label": "BLITZ on a funded 50K next to LIT (PAPER)",
                         "stage": "trade" if op50 and op50.get("exit_kind") == "OPEN" else "flat", "text": f_state + (" · " + f_txt if f_txt else ""),
                         "paper": True}],
            "lines": lines, "marks": marks, "signals": signals, "band": band, "position": pos or pos50, "position50": pos50, "eval": ev, "money": m,
            "funded50": {"account": a5, "money": m5, "today": f50.get("today") or []}, "trades": c.get("today") or [],
            "thinking": {"headline": st.get("text"), "stage": st.get("stage"), "eval": ev_txt, "funded50": f_txt},
            "text": "PAPER only: never routed to an account. " + " · ".join(x for x in (ev_txt, f_txt) if x), "t": c.get("t")}


# ---------------------------------------------------------------------------------------------- the whole view
def view(bot, tf: str = "1m", now: int | None = None, narr: N.Narrator | None = None, n_feed: int = 100) -> dict:
    now = int(now or _now(bot))
    tf = "5m" if tf == "5m" else "1m"
    B = bars(bot, tf, now)
    st = getattr(bot, "state", None) or {}
    price = _f(st.get("price")) or (B["bars"][-1][4] if B["bars"] else None)
    narr = narr if narr is not None else N.NARRATOR
    narr.observe(bot, now)                                     # no pushes, no files: just today's feed fresh for the page
    h = getattr(bot, "health", None) or {}
    out = {"t": now, "tf": tf, "day": B["day"], "t0": B["t0"], "t1": B["t1"], "bars": B["bars"], "source": B["source"], "price": price,
           "running": bool(getattr(bot, "running", False)), "kill": bool(getattr(bot, "kill", False)),
           "adapter": str((getattr(bot, "cfg", None) or {}).get("adapter") or "paper"),
           "feed": {"stale": bool(h.get("stale")), "age_s": h.get("data_age_s"), "source": h.get("data_source"),
                    "entries_blocked": bool(h.get("entries_blocked"))},
           "strategies": {}}
    try:
        out["account"] = bot._push_account() if callable(getattr(bot, "_push_account", None)) else None
    except Exception:
        out["account"] = None
    try:
        out["strategies"]["lit"] = lit_layer(bot, now, price)
    except Exception as e:
        out["strategies"]["lit"] = {"key": "lit", "name": "Zlarior", "color": COLORS["lit"], "error": f"{e.__class__.__name__}: {e}"[:200]}
    try:
        out["strategies"].update(atlas_layer(bot, now, B["hist5"], B["t0"], price))
    except Exception as e:
        out["strategies"]["atlas"] = {"key": "atlas", "name": "ATLAS", "color": COLORS["atlas"], "error": f"{e.__class__.__name__}: {e}"[:200]}
    try:                                                       # BLITZ (strategy 3) fills the purple layer once it runs (PAPER)
        bl = blitz_layer(bot, now, price)
        if bl:
            sc = out["strategies"].get("scalp") or {"key": "scalp", "color": COLORS["scalp"], "members": []}
            others = [m for m in sc.get("members") or [] if m.get("key") != "blitz"]
            out["strategies"]["scalp"] = {**sc, **bl, "key": "scalp", "color": COLORS["scalp"], "placeholder": False,
                                          "members": bl["members"] + others}
    except Exception as e:
        out["strategies"].setdefault("scalp", {"key": "scalp", "color": COLORS["scalp"]})["error"] = f"BLITZ: {e.__class__.__name__}: {e}"[:200]
    try:                                                       # market structure (engine/structure.py, read-only advice)
        out["structure"] = structure_block(bot, now, price)
    except Exception as e:
        from . import structure as ST
        out["structure"] = {**ST.block([], [], now=now, key="err"), "summary": f"Structure unavailable: {e.__class__.__name__}"[:160]}
    try:
        _structure_notes(out, bot, now)
    except Exception:
        pass
    out["narrator"] = narr.feed(n_feed)
    out["push_kinds"] = {k: {"label": v[0], "on": on} for (k, v), on in zip(N.KINDS.items(), N.push_prefs().values())}
    return out


# ---------------------------------------------------------------------------------------------- market structure
_SB: dict = {}


def structure_block(bot, now: int, price=None) -> dict:
    """The "structure" block (engine/structure.block: 5m / 15m / 1h trend, last BOS / CHoCH, swings, protected swings, pools,
    premium / discount, per-strategy bias) from the bot's own bars: the LIT 1m store (12 days) + bars_tail (5m); without
    them the TradingView export (data/NQ_1m.csv, the last 12 days up to now) when the CSV fallback is on. Cached on the
    bot's last bars (the rows are only rebuilt when a bar closed)."""
    from . import pcdash_api
    from . import structure as ST
    st = getattr(bot, "_lit_1m_store", None)
    tail = getattr(bot, "bars_tail", None) or []
    try:
        l1 = (len(st), int(st["time"].iloc[-1])) if st is not None and len(st) else (0, None)
    except Exception:
        l1 = (0, None)
    last5 = tail[-1] if tail else None
    sig = (id(bot), l1, len(tail), (last5.get("time") if isinstance(last5, dict) else (last5[0] if last5 else None)))
    hit = _SB.get("v")
    t_now = int(now)
    if hit and hit[0] == sig and t_now // 60 == hit[1] // 60:
        A = hit[2]                                             # same bars, same minute: no rows rebuilt, no recompute
    else:
        b5, b1 = pcdash_api.bot_bars(bot, now - 15 * 86400)
        if not b1 and not b5 and CSV_FALLBACK:
            df = pcdash_api._csv("NQ", "1m")
            if df is not None and len(df):
                end = min(int(now), int(df["time"].iloc[-1]) + 60)
                b1 = pcdash_api._rows_from_frame(df[(df["time"] >= end - 12 * 86400) & (df["time"] < end)])
                t_now = end if not getattr(bot, "running", False) else t_now
        A = ST.analyze(ST.closed_only(b1, 60, t_now), ST.closed_only(b5, 300, t_now), t_now, None)
        _SB["v"] = (sig, int(now), A)
    return ST.block_from(A, int(now), price)


def _structure_notes(out: dict, bot, now: int):
    """One structure line + the playbook rule in each strategy's thinking panel (advice only), and for an open Zlarior trade the
    discretion advisor's live notes (engine/advisor.advise_open: what a structure trader would do, never an order)."""
    from . import playbook as PB
    S = out.get("structure") or {}
    ps = S.get("per_strategy") or {}
    strats = out.get("strategies") or {}
    lit_ = strats.get("lit") or {}
    th = lit_.get("thinking")
    if isinstance(th, dict):
        th["structure"] = (ps.get("lit") or {}).get("note")
        th["rule"] = PB.now("lit", {"brain": getattr(bot, "brain", None), "position": lit_.get("position"), "now": now})
        pos = lit_.get("position")
        if isinstance(pos, dict) and pos.get("entry") is not None and pos.get("entry_t"):
            try:
                from . import advisor as AD, pcdash_api
                _, b1 = pcdash_api.bot_bars(bot, int(pos["entry_t"]) - 6 * 86400)
                adv = AD.advise_open("lit", {**pos, "dir": int(pos.get("dir") or (1 if pos.get("side") == "LONG" else -1))}, b1, now)
                th["advice"] = [{"t": a["t"], "rule": a["rule"], "text": a["why"], "playbook": a.get("playbook")} for a in adv[:3]]
            except Exception:
                th["advice"] = []
    at = strats.get("atlas")
    if isinstance(at, dict):
        mem = {m.get("key"): {"stage": m.get("stage"), "text": m.get("text")} for m in at.get("members") or [] if isinstance(m, dict)}
        at["structure_note"] = (ps.get("atlas") or {}).get("note")
        at["rule"] = PB.now("atlas", {"members": mem})
    sc = strats.get("scalp")
    if isinstance(sc, dict):
        sc["structure_note"] = (ps.get("scalp") or {}).get("note")
        thb = sc.get("thinking") if isinstance(sc.get("thinking"), dict) else None
        if thb is not None:
            thb["structure"] = sc["structure_note"]
        sc["rule"] = PB.now("scalp", {"stage": (thb or {}).get("stage"), "text": (thb or {}).get("headline")})


# ---------------------------------------------------------------------------------------------- phone (liveview.json)
PHONE_FILE = "liveview.json"
PHONE_KIND = "le-liveview"
PHONE_MAX = 240 * 1024        # bytes; the 1m bars go first, then the feed
PHONE_N1 = 480                # 1m bars on the phone (8 hours); the 5m session goes whole as "bars5"
PHONE_FEED = 60


def phone_view(bot, now: int | None = None, narr: N.Narrator | None = None) -> dict:
    """liveview.json, the phone's Live View (tools/web_public/liveview.js; owner 2026-10-28: "add it to the phone too").
    engine/live_publish pushes it next to live.json every minute. The PC page's view() on 1m (last PHONE_N1 bars) plus
    today's 5m session as "bars5" (the phone switches 1m / 5m without asking the PC), the feed cut to PHONE_FEED, trimmed
    under PHONE_MAX. The same read-only layers as the PC page. Never raises."""
    t = int(now or _now(bot))
    try:
        v = view(bot, "1m", t, narr, n_feed=PHONE_FEED)
        try:
            v["bars5"] = bars(bot, "5m", v["t"])["bars"]
        except Exception:
            v["bars5"] = []
        v["bars"] = (v.get("bars") or [])[-PHONE_N1:]
        v.update(kind=PHONE_KIND, v=1)

        def size():
            return len(json.dumps(v, separators=(",", ":"), default=str))
        while size() > PHONE_MAX and len(v["bars"]) > 120:
            v["bars"] = v["bars"][-max(120, len(v["bars"]) * 2 // 3):]
            v["trimmed"] = True
        while size() > PHONE_MAX and len(v.get("narrator") or []) > 10:
            v["narrator"] = v["narrator"][:len(v["narrator"]) // 2]
            v["trimmed"] = True
        return v
    except Exception as e:
        return {"kind": PHONE_KIND, "v": 1, "t": t, "error": f"{e.__class__.__name__}: {e}"[:200]}


@router.get("/api/next/liveview")
def r_view(tf: str = "1m"):
    try:
        return _J(view(_bot(), tf))
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {e}"[:200]}, 500)


@router.get("/api/next/liveview/feed")
def r_feed(after: int | None = None, n: int = 100, strat: str = ""):
    try:
        bot = _bot()
        N.NARRATOR.observe(bot)
        return _J({"t": _now(bot), "feed": N.NARRATOR.feed(n, after=after, strat=strat or None)})
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {e}"[:200]}, 500)
