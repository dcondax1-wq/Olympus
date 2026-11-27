"""Brain feed (day-brain-feed 2026-11-24; READ-ONLY: it never trades, never sizes, never arms, never writes a file).

The Brain app (tools/web_public brain app, day-brain-app) shows for each bot what trade is coming, what it is thinking and the
levels it watches. This module builds one small block for the PC's 15-minute report (tools/pc_report.full -> ext block "bf",
after every other block: EXT_LAST) from what the bots ALREADY computed and the heartbeat already carries:

  lit    engine/brain.compact (hb["brain"]): stages, setups + plans, log, nearest / taken levels, VIX band
  atlas  engine/second.compact (hb["second"]): per strategy state, brain plan, checks, log, S/R levels
  blitz  engine/blitz.compact (hb["blitz"]): state text, today's band checks, signals, the open PAPER trade (hidden bot, paper)
  of     the order-flow recorder / study (data/tickrec.json, data/orderflow_auto.json, data/orderflow_note.json, data/ticks/)
  market today's NQ 5m bars (the PC's NinjaTrader LE_BarFeed files, tools/pc_report.bar_files) + the LIT brain's VIX band

Shape (docs/BRAIN_FEED_PC.md): {"v", "t", "market": {...}, "bots": {id: {"think": [...], "next": {...}, "levels": [...]}}}.
Every part is built in its own try/except: one broken bot gives {"err": "..."} for that bot, never an exception. Under MAX_BYTES
(fit() cuts think lines, then levels, then steps, then texts).

    python -X utf8 -m engine.brain_feed [heartbeat.json]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time

VERSION = 1
MAX_BYTES = 2000             # the whole block (all bots + market): the ext post's room after the other blocks (pc_report MAX_STATUS_BYTES 3800)
THINK_N = {"lit": 8, "atlas": 8, "blitz": 4, "of": 5}       # day-oflearn: 3 -> 5 (+ the OF paper line, + the learner line)
LEVELS_N = 12
LINE_N = 64                  # one thought line, characters
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001
    ET = None

# market phase rules (documented in docs/BRAIN_FEED_PC.md "market")
PHASE_BARS = 6               # the last 30 minutes (6 x 5m bars)
EXPAND_NET_X = 1.5           # expanding: a new day high / low inside the last 6 bars AND |net move of those bars| >= 1.5 x the day's mean 5m bar range
RETRACE_FRAC = 0.30          # retracing: price has come back >= 30% of today's range from the extreme made last
MIN_BARS = 6


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


def _p(v):
    """A price, 2 decimals (quarter ticks stay exact); None stays None."""
    v = _f(v)
    return None if v is None else round(v, 2)


def _num(v) -> str:
    v = _f(v)
    if v is None:
        return "-"
    return f"{v:,.2f}".rstrip("0").rstrip(".") if abs(v - round(v)) > 1e-9 else f"{v:,.0f}"


def _t(s, n=LINE_N) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _hm(t) -> str:
    t = _f(t)
    if not t or t <= 0:
        return ""
    try:
        return dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M") if ET else time.strftime("%H:%M", time.localtime(int(t)))
    except Exception:  # noqa: BLE001
        return ""


def _plain(s) -> str:
    """A brain log line in short plain words: the parenthesised detail, ticks / crosses and 'LIT |' pipes out, first letter small."""
    s = str(s or "")
    s = re.sub(r"\s*\([^()]*\)", "", s)
    s = s.replace("✓", "").replace("✗", "").replace(" | ", " ").replace("Now: ", "")
    s = re.sub(r"(\d),(\d{3})\.(\d+)", lambda m: m.group(1) + "," + m.group(2) + ("." + m.group(3) if m.group(3).strip("0") else ""), s)
    s = re.sub(r"\s+", " ", s).strip(" :;-")
    return s[:1].lower() + s[1:] if s[:2] != s[:2].upper() else s


def _line(hm, text) -> str:
    return _t(((str(hm) + " ") if hm else "") + str(text or ""))


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items() if v not in (None, "", [], {})}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return o


def _lv(kind, price, label) -> dict | None:
    p = _p(price)
    return None if p is None else {"kind": kind, "price": p, "label": _t(label, 22)}


def _uniq_levels(rows, n=LEVELS_N) -> list:
    out, seen = [], set()
    for r in rows:
        if not r:
            continue
        k = (r["kind"], r["price"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out[:n]


# ------------------------------------------------------------------------------------------------ LIT (Zlarior)
ARMED = ("armed", "tapped", "entering")


def _lit_setup(br):
    """The setup that is coming: an armed limit first, else the newest filled one while in the trade."""
    S = [s for s in _l(br.get("setups")) if isinstance(s, dict)]
    for s in reversed(S):
        if s.get("status") in ARMED:
            return s
    if br.get("trade"):
        for s in reversed(S):
            if s.get("status") == "filled":
                return s
    return None


def lit_bot(br: dict, mk: dict | None = None) -> dict:
    br = _d(br)
    if not br:
        return {}
    st = _d(br.get("stage"))
    px = _f(br.get("price"))
    vix = _d(_d(br.get("guards")).get("vix"))
    s = _lit_setup(br)
    pl = _d(_d(s).get("plan"))
    tr = _d(br.get("trade"))
    watch = next((w for w in _l(br.get("watch")) if isinstance(w, dict) and w.get("text") and w.get("allowed", True)), None)
    # think: what it is doing NOW first (ET time of the brain), then the newest log lines
    now_hm = str(br.get("bar_hm") or "") if not br.get("at") else str(br.get("at")).split(" ")[-2] if " ET" in str(br.get("at")) else ""
    think = []
    if s and s.get("status") in ARMED:
        think.append(_line(now_hm, f"{s.get('side', '').lower()} limit {_num(pl.get('limit'))} armed, stop {_num(pl.get('stop'))}"))
    elif watch:
        need = re.search(r"Waiting for (.+?)(?:\.(?:\s|$)|$)", str(watch.get("text")))
        think.append(_line(now_hm, "waiting for " + _plain(need.group(1) if need else watch.get("text"))))
    elif st.get("waiting"):
        think.append(_line(now_hm, _plain(st.get("waiting"))))
    if _f(vix.get("vix")) is not None and _f(vix.get("move")) is not None:
        rr = _f(pl.get("rr"))
        think.append(_line(now_hm, f"VIX {_f(vix['vix']):.1f} -> day move {_f(vix['move']):.0f} pts"
                                   + (f" -> target {rr:.1f}R" if rr is not None else "")))
    for r in _l(br.get("log")):
        if isinstance(r, dict) and r.get("text") and r.get("kind") != "stage":
            think.append(_line(r.get("hm"), _plain(r.get("text"))))
        if len(think) >= THINK_N["lit"]:
            break
    # next
    stages = [{"name": str(k), "done": stt == "done"} for k, stt in (x for x in _l(br.get("stages")) if isinstance(x, (list, tuple)) and len(x) >= 2)]
    lim = _f(pl.get("limit"), _f(tr.get("entry")))
    dist = None
    if px is not None and lim is not None and not tr:
        dist = round(abs(px - lim), 2)
    elif watch:
        m = re.search(r"([\d.]+) pts away", str(watch.get("text")))
        dist = _f(m.group(1)) if m else None
    win = (f"until {pl['expires_hm']} ET" if pl.get("expires_hm") and not tr else
           _d(_d(br.get("guards")).get("market")).get("window"))
    done = st.get("key") in ("done", "closed") and not tr
    if done:
        watch, dist = None, None
    side = (s or {}).get("side") or (watch or {}).get("side") or ({1: "LONG", -1: "SHORT"}.get(st.get("dir")) if st.get("dir") else None)
    swept = ", ".join(str(x) for x in _l((s or {}).get("swept"))[:2])
    nx = {"setup": "done for today" if done else _t(" ".join(x for x in (str(side or ""), "sweep + shift", ("of " + swept) if swept else "") if x), 48),
          "steps": stages, "waiting_for": _t(st.get("waiting"), 110), "dist_pts": dist, "window": win,
          "limit": _p(lim), "stop": _p(pl.get("stop", tr.get("stop"))), "target": _p(pl.get("target", tr.get("target")))}
    if not s and not tr:                          # nothing armed: no limit / stop / target to show (the steps + waiting say why)
        nx.update(limit=None, stop=None, target=None)
    # levels: the trade's stop / target, today's swept levels, the VIX band, the day's retrace, the nearest untaken pools
    rows = [_lv("stop", nx["stop"], "stop"), _lv("target", nx["target"], pl.get("target_label") or "target"),
            _lv("expansion", vix.get("up"), "VIX band up"), _lv("expansion", vix.get("dn"), "VIX band down")]
    mk = _d(mk)
    if mk.get("mid") is not None:
        rows.append(_lv("retrace", mk["mid"], "50% of today"))
    near = lambda r: abs((_f(r.get("price")) or 0) - (px or 0))
    lv = [r for r in _l(br.get("levels")) if isinstance(r, dict) and _f(r.get("price")) is not None]
    for r in sorted([r for r in lv if r.get("taken")], key=near)[:4]:       # today's swept levels, the nearest 4
        rows.append(_lv("sweep", r.get("price"), f"{r.get('label')} {r.get('taken_hm') or ''}".strip()))
    for r in sorted([r for r in lv if not r.get("taken")], key=near)[:3]:   # the nearest untaken pools / gaps
        rows.append(_lv("fvg" if r.get("kind") == "gap" else "liq", r.get("price"), r.get("label")))
    return {"think": think[:THINK_N["lit"]], "next": nx, "levels": _uniq_levels(rows)}


# ------------------------------------------------------------------------------------------------ ATLAS (3 lobes, second.py)
def atlas_bot(sec: dict, px=None) -> dict:
    S = _d(_d(sec).get("strategies"))
    if not S:
        return {}
    ab = _d(_d(_d(sec).get("route")).get("account_b"))
    keys = [k for k in _l(ab.get("keys")) if k in S] or [k for k, v in S.items() if _d(v).get("route")] or \
        [k for k, v in S.items() if _d(v).get("brain") and not _d(v).get("candidate")]
    logs, cand, rows = [], None, []
    for k in keys:
        s = _d(S.get(k))
        b = _d(s.get("brain"))
        short = str(s.get("short") or k)
        stt = _d(s.get("state"))
        for x in _l(b.get("log"))[-4:]:
            if isinstance(x, dict) and x.get("text"):
                logs.append((_f(x.get("t"), 0) or 0, _line(_hm(x.get("t")), f"{short}: {_plain(x['text'])}")))
        pl = _d(b.get("plan"))
        if pl and stt.get("stage") not in ("off", "error", "done") and (cand is None or stt.get("stage") == "in_trade"):
            cand = (k, short, s, b, pl)
        for lv in _l(b.get("levels"))[:6]:
            if isinstance(lv, dict) and _f(lv.get("px")) is not None and lv.get("stage") not in ("used",):
                swept = "swept" in str(lv.get("stage") or "") or "reclaim" in str(lv.get("stage") or "")
                rows.append((abs((_f(lv["px"]) or 0) - (_f(px) or 0)), _lv("sweep" if swept else "liq", lv["px"], f"{short} {lv.get('name') or ''}")))
    logs.sort(key=lambda z: -z[0])
    think = []
    for k in keys:                                # each lobe's state in one line first
        s = _d(S.get(k))
        txt = _d(s.get("state")).get("text")
        if txt:
            think.append(_line("", f"{s.get('short') or k}: {_plain(txt)}"))
    think = (think[:3] + [x[1] for x in logs])[:THINK_N["atlas"]]
    nx = {}
    if cand:
        k, short, s, b, pl = cand
        steps = [{"name": _t(c.get("name") or c.get("k"), 18), "done": bool(c.get("ok"))} for c in _l(b.get("checks")) if isinstance(c, dict)][:8]
        e = _f(pl.get("entry"))
        nx = {"setup": _t(f"{short} {str(pl.get('side') or '').upper()}", 48), "steps": steps,
              "waiting_for": _t(b.get("first_fail") or _d(s.get("state")).get("text") or b.get("text"), 110),
              "dist_pts": round(abs(_f(px) - e), 2) if None not in (_f(px), e) else None,
              "window": _t(pl.get("when"), 40), "limit": _p(e), "stop": _p(pl.get("stop")), "target": _p(pl.get("target"))}
    lv = [_lv("stop", nx.get("stop"), "stop"), _lv("target", nx.get("target"), "target")] + [r[1] for r in sorted(rows, key=lambda z: z[0])]
    return {"think": think, "next": nx, "levels": _uniq_levels(lv, 8)}


# ------------------------------------------------------------------------------------------------ BLITZ (paper, hidden)
def blitz_bot(bz: dict, px=None) -> dict:
    bz = _d(bz)
    if not bz:
        return {}
    st = _d(bz.get("state"))
    think = [_line("", _plain(st.get("text")))] if st.get("text") else []
    for x in reversed(_l(bz.get("signals"))):
        if isinstance(x, dict):
            side = "long" if (_f(x.get("dir"), 0) or 0) > 0 else "short"
            think.append(_line(_hm(x.get("close_t") or x.get("t")), f"signal {side} close {_num(x.get('close'))}"
                               + (" taken" if x.get("taken") else f" skipped: {_plain(x.get('why'))}" if x.get("why") else "")))
    for r in reversed(_l(bz.get("today"))):
        if isinstance(r, dict) and r.get("exit_kind") and r.get("exit_kind") != "OPEN":
            think.append(_line(_hm(r.get("exit_t")), f"paper {str(r.get('side') or '').lower()} closed {r.get('exit_kind')} {_f(r.get('r'), 0):+.2f}R"))
    op = _d(bz.get("open"))
    band = _d(bz.get("band"))
    nxt = None
    m = re.search(r"Next check (\d\d:\d\d)", str(st.get("text") or ""))
    if m:
        nxt = next((c for c in _l(band.get("checks")) if isinstance(c, dict) and c.get("hm") == m.group(1)), None)
    up, lo = _f(_d(nxt).get("up")), _f(_d(nxt).get("lo"))
    dist = None
    if _f(px) is not None and (up is not None or lo is not None):
        dist = round(min(abs(_f(px) - v) for v in (up, lo) if v is not None), 2)
    nx = {"setup": "PAPER noise-band breakout" + (f" ({'long' if (_f(op.get('dir'), 0) or 0) > 0 else 'short'} open)" if op else ""),
          "steps": [{"name": "09:30 open", "done": band.get("o0") is not None}, {"name": "day filter", "done": st.get("stage") not in ("filtered",)},
                    {"name": "band close", "done": bool(op)}],
          "waiting_for": _t(st.get("text"), 110), "dist_pts": None if op else dist,
          "window": (m.group(1) + " ET check") if m else None,
          "limit": _p(op.get("entry")) if op else None, "stop": _p(op.get("stop_now", op.get("stop"))) if op else None, "target": None}
    rows = [_lv("stop", nx["stop"], "paper stop"), _lv("expansion", up, f"band up {m.group(1)}" if m else "band up"),
            _lv("expansion", lo, f"band down {m.group(1)}" if m else "band down")]
    return {"think": think[:THINK_N["blitz"]], "next": nx, "levels": _uniq_levels(rows, 4), "paper": True}


# ------------------------------------------------------------------------------------------------ ORDER FLOW (recorder + study)
def _rj(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


def _of_live(br: dict | None) -> list:
    """day-ofmax: the live PAPER read (engine/oflive, stdlib only): delta of the last 5 / 15 minutes and, when LIT has an armed
    setup, OF1's zone read at its sweep extreme (the plan's stop is 1 tick beyond it). [] when there is no live tick file."""
    try:
        from engine import oflive
    except Exception:  # noqa: BLE001
        return []
    lvl, d = None, 0
    s = _lit_setup(_d(br)) if br else None
    if s and s.get("status") in ARMED:
        st = _f(_d(s.get("plan")).get("stop"))
        d = 1 if str(s.get("side", "")).upper().startswith("L") else -1 if str(s.get("side", "")).upper().startswith("S") else 0
        if st is not None and d:
            lvl = st + d * 0.25
    r = oflive.live_read(lvl, d)
    if not r or r.get("age_s", 9999) > 900:
        return []
    who = lambda x: "buyers" if x > 0 else "sellers" if x < 0 else "even"
    out = [_line(_hm(r["t"]), f"flow 5m {r['d5']:+,} of {r['v5']:,} ({who(r['d5'])}), 15m {r['d15']:+,}")]
    lv = r.get("level")
    if lv:
        side = "long" if lv["d"] == 1 else "short"
        out.append(_line(_hm(r["t"]), f"LIT {side} lvl {_num(lv['px'])}: {lv['vz']:,} lots, delta {lv['dz']:+,}: {lv['read']}"))
    return out


def of_bot(root: str | None = None, br: dict | None = None) -> dict:
    """The order-flow lane: not a trading bot yet (research, engine/tickrec.py). Plain JSON reads + one listdir, no tickrec import.
    day-ofmax: + the live paper read (engine/oflive) and the newest journal line (data/orderflow_journal.jsonl)."""
    root = root or ROOT
    on = bool(_d(_rj(os.path.join(root, "data", "tickrec.json"))).get("enabled")) or os.environ.get("OLYMPUS_TICKREC") == "1"
    auto = _d(_rj(os.path.join(root, "data", "orderflow_auto.json")))
    note = _d(_rj(os.path.join(root, "data", "orderflow_note.json")))
    try:
        days = len({f.split(".")[0] for f in os.listdir(os.path.join(root, "data", "ticks")) if re.match(r"\d{4}-\d\d-\d\d\.", f)})
    except OSError:
        days = 0
    runs = [r for r in _l(auto.get("runs")) if isinstance(r, dict)]
    learned = any(os.path.exists(os.path.join(root, *p)) for p in (("logs", "orderflow", "of_learn_state.json"),
                                                                  ("research", "learn", "of_learn_state.json"), ("data", "of_paper.json")))
    if not on and not days and not runs and not note and not learned:
        return {}
    live = _of_live(br) if on else []
    think = live + [_line("", f"tick recorder {'on' if on else 'off'}, {days} tick days stored (study at 60)")]
    try:
        from engine import oflive
        tl = oflive.journal_tally(os.path.join(root, "data", "orderflow_journal.jsonl"))
        if tl.get("last"):
            think.insert(len(live), _line("", _plain(tl["last"]) + (f" | flow right {tl['right']} of {tl['judged']}" if tl["judged"] else "")))
    except Exception:  # noqa: BLE001
        pass
    ofp = _d(_rj(os.path.join(root, "data", "of_paper.json")))      # day-oflearn: the pillar's PAPER bot (engine/of_paper.py)
    today_et = dt.datetime.now(ET).strftime("%Y-%m-%d") if ET is not None else None
    if ofp.get("line") and ofp.get("day") == today_et:
        think.insert(len(live), _line(_hm(ofp.get("t")), _plain(ofp["line"])))
    olane = _d(_rj(os.path.join(root, "data", "of_lane_state.json")))    # day-ofready2: the Sim lane (engine/of_lane.py)
    if olane.get("line") and olane.get("day") == today_et:
        think.insert(len(live), _line(_hm(olane.get("t")), _plain(olane["line"])))
    for lp in (os.path.join(root, "logs", "orderflow", "of_learn_state.json"), os.path.join(root, "research", "learn", "of_learn_state.json")):
        ln = _d(_rj(lp)).get("line")                     # day-oflearn: the nightly learner's newest line (research/orderflow/of_learn.py)
        if ln:
            think.append(_line("", "learner: " + _plain(ln)))
            break
    if runs:
        think.append(_line("", f"study looks done: {len(runs)} of 2, last at {runs[-1].get('days')} days"))
    if note.get("body"):
        think.append(_line(_hm(note.get("t")), _plain(note["body"])))
    nx = {"setup": "order-flow study (research, no trades)",
          "steps": [{"name": "recorder on", "done": on}, {"name": "60 NQ tick days", "done": days >= 60}, {"name": "study run", "done": bool(runs)}],
          "waiting_for": ("the study result" if days >= 60 and not runs else f"{max(0, 60 - days)} more NQ tick days") if not note else "your yes on a PASS (none = LIT stays)",
          "window": "outside 02:00-16:05 ET"}
    return {"think": think[:THINK_N["of"]], "next": nx, "levels": [], "paper": True}


# ------------------------------------------------------------------------------------------------ market
def _et_day_start(now: int) -> int:
    """The CME day's start (18:00 ET the evening before) for unix now."""
    if ET is None:
        return int(now) - int(now) % 86400
    d = dt.datetime.fromtimestamp(int(now), ET)
    s = d.replace(hour=18, minute=0, second=0, microsecond=0)
    if d < s:
        s -= dt.timedelta(days=1)
    return int(s.timestamp())


def market(bars, now=None, br: dict | None = None) -> dict:
    """{phase, today_range_pts, where_in_range_pct, regime (+ mid: the day's 50%, for LIT's retrace level)} from today's 5m bars
    [(t, o, h, l, c)] (since 18:00 ET). Rules: docs/BRAIN_FEED_PC.md. Without bars only the regime (from the VIX band)."""
    br = _d(br)
    vix = _d(_d(br.get("guards")).get("vix"))
    v = _f(vix.get("vix"))
    regime = None
    if v is not None:
        regime = ("calm" if v < 15 else "normal" if v < 20 else "high vol" if v < 28 else "extreme") + f" (VIX {v:.1f})"
    out = {"regime": regime}
    rows = [r for r in _l(bars) if isinstance(r, (list, tuple)) and len(r) >= 5]
    if rows:
        now = int(now or rows[-1][0] + 300)
        a = _et_day_start(now)
        rows = [r for r in rows if a <= int(r[0]) <= now]
    if len(rows) < MIN_BARS:
        return _clean(out)
    hi, lo = max(r[2] for r in rows), min(r[3] for r in rows)
    rng = hi - lo
    px = _f(br.get("price"), rows[-1][4])
    last = rows[-PHASE_BARS:]
    mean_bar = sum(r[2] - r[3] for r in rows) / len(rows)
    i_hi = max(range(len(rows)), key=lambda i: (rows[i][2], i))
    i_lo = max(range(len(rows)), key=lambda i: (-rows[i][3], i))
    new_ext = max(i_hi, i_lo) >= len(rows) - PHASE_BARS
    net = abs(last[-1][4] - last[0][1])
    back = ((hi - px) if i_hi > i_lo else (px - lo)) / rng if rng > 0 else 0.0
    if new_ext and mean_bar > 0 and net >= EXPAND_NET_X * mean_bar:
        phase = "expanding"
    elif back >= RETRACE_FRAC:
        phase = "retracing"
    else:
        phase = "ranging"
    out.update(phase=phase, today_range_pts=round(rng, 2), where_in_range_pct=int(round(100 * (px - lo) / rng)) if rng > 0 else 50,
               mid=_p(lo + rng / 2))
    mv = _f(vix.get("move"))
    if mv:
        out["range_vs_move_pct"] = int(round(100 * rng / mv))
    return _clean(out)


# ------------------------------------------------------------------------------------------------ build + fit
def build(hb: dict | None, bars=None, root: str | None = None, now=None, max_bytes: int = MAX_BYTES) -> dict | None:
    """The feed block of one heartbeat (+ today's 5m bars). None without a heartbeat. Never raises."""
    try:
        hb = _d(hb)
        if not hb:
            return None
        br = _d(hb.get("brain"))
        px = _f(br.get("price"), _f(hb.get("price")))
        try:
            mk = market(bars, now=now, br=br)
        except Exception as e:  # noqa: BLE001
            mk = {"err": e.__class__.__name__}
        bots = {}
        for bid, fn in (("lit", lambda: lit_bot(br, mk)), ("atlas", lambda: atlas_bot(hb.get("second"), px)),
                        ("blitz", lambda: blitz_bot(hb.get("blitz"), px)), ("of", lambda: of_bot(root, br))):
            try:
                b = fn()
            except Exception as e:  # noqa: BLE001
                b = {"err": f"{e.__class__.__name__}: {_t(e, 60)}"}
            if b:
                bots[bid] = _clean(b)
        mk.pop("mid", None)
        out = {"v": VERSION, "t": int(_f(hb.get("t"), now or time.time())), "market": mk, "bots": bots}
        return fit(out, max_bytes)
    except Exception as e:  # noqa: BLE001
        return {"v": VERSION, "err": f"{e.__class__.__name__}: {_t(e, 80)}"}


def size(o) -> int:
    return len(json.dumps(o, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8"))


ORDER = ("of", "blitz", "atlas", "lit")      # who gives up room first


def fit(g: dict, max_bytes: int = MAX_BYTES) -> dict:
    """Cut least needed first: the lesser bots' think lines and levels, then LIT's, then step lists, then texts."""
    bots = _d(g.get("bots"))
    steps = [("think", {"of": 1, "blitz": 2, "atlas": 5, "lit": 8}), ("levels", {"blitz": 2, "atlas": 4, "lit": 10}),
             ("think", {"atlas": 4, "lit": 6}), ("levels", {"atlas": 2, "lit": 8}), ("think", {"blitz": 1, "atlas": 3, "lit": 5}),
             ("levels", {"lit": 6, "atlas": 0, "blitz": 0}), ("steps", None), ("think", {"of": 0, "blitz": 1, "atlas": 2, "lit": 4})]
    for key, lim in steps:
        if size(g) <= max_bytes:
            return g
        g["trimmed"] = True
        for bid, b in bots.items():
            if key == "steps":
                nx = _d(b.get("next"))
                if isinstance(nx.get("steps"), list):        # [{name, done}] -> "3/10" (how far it got)
                    nx["steps"] = f"{sum(1 for s in nx['steps'] if _d(s).get('done'))}/{len(nx['steps'])}"
            elif isinstance(b.get(key), list) and bid in lim:
                b[key] = b[key][:lim[bid]]
    for n in (44, 32):
        if size(g) <= max_bytes:
            return g
        for b in bots.values():
            b["think"] = [_t(x, n) for x in _l(b.get("think"))]
            nx = _d(b.get("next"))
            if isinstance(nx.get("waiting_for"), str):
                nx["waiting_for"] = _t(nx["waiting_for"], n + 16)
    for bid in ORDER:                         # last resort: whole bots out, the lesser first (LIT stays)
        if size(g) <= max_bytes or bid == "lit":
            break
        bots.pop(bid, None)
    for th, lv in ((3, 4), (2, 3), (1, 2), (0, 0)):   # LIT alone still too big: its next stays whole, the rest goes
        if size(g) <= max_bytes:
            break
        for b in bots.values():
            b["think"], b["levels"] = _l(b.get("think"))[:th], _l(b.get("levels"))[:lv]
    return g


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -X utf8 -m engine.brain_feed <heartbeat.json>")
        return 2
    with open(argv[0], encoding="utf-8") as fh:
        hb = json.load(fh)
    out = build(hb)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    print("bytes:", size(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
