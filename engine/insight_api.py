"""AI Insights page (owner's 50-feature list, group C, items 21-30) for the PC dashboard (web_next/js/next/insight.js).

One read-only GET built from data the bot already has. Nothing here starts, arms, routes, sizes, stops or writes anything:

  GET /api/next/insight                 the live view: the PC bot's last Bot Brain (engine/brain.py) and ATLAS run
                                        (LiveBot.second, engine/second.py) when it runs; otherwise the last stored session
                                        replayed from the stored bars (brain.replay + second.run on data/NQ_5m.csv)
  GET /api/next/insight?day=YYYY-MM-DD&hm=HH:MM   that 2026 session replayed at that ET minute (18:00-23:59 = the evening before)

Panels (each built on its own: one failing panel returns {"error"} and never breaks the others):
  radar      21  what Zlarior (LIT) and each ATLAS member waits for now and how far price is from the trigger
  windows    22  next entry window per strategy (open now / opens in), weekends skipped (CME holidays not counted)
  scorecard  23  live vs backtest per strategy: Zlarior on engine/health_band (run lit_live H2 band, via ai_watch.drift_lit),
                 ATLAS members on engine/second_scorecard (2026 H2 bootstrap), research H1 / H2 numbers next to them
  drift      24  the AI watch block (engine/ai_watch.py hb_block; else drift_lit / drift_b / drift_exec computed here)
  grade      25  the trader's A/B/C grade (engine/lit_learn.trader_grade's 4 points) of the current / last setup
  similar    26  2026 trades with the same grade + entry session (+ the same loss cause) from the LIT journal
                 (data/lit_journal.jsonl), else run lit_live's trades of the same session: win rate, avg R, $
  regime     27  VIX / VXN and the VIX band, 15m / 1h EMA 21 vs 50 trend, next high-impact news, Asia / London ranges
  levels     28  today's LIT levels from the Brain: swept (when, how deep) and untouched (distance)
  atlas      29  each ATLAS member's state text, today's trades, last trade, research H2 numbers
  strategy3  30  the scalp research slot: research/writeups/scalp-*.md front matter / research/scalp/*.json, else "in research"
"""
from __future__ import annotations

import collections
import datetime as dt
import glob
import json
import math
import os
import re
import threading
import time
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import Response

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = ZoneInfo("America/New_York")
# every input path is a module constant so tests can point it at temp files
JOURNAL = os.path.join(ROOT, "data", "lit_journal.jsonl")
RUNS = os.path.join(ROOT, "research", "runs")
SECOND_DIR = os.path.join(ROOT, "research", "second")
WRITEUPS = os.path.join(ROOT, "research", "writeups")
SCALP_DIR = os.path.join(ROOT, "research", "scalp")
BARS_5M = os.path.join(ROOT, "data", "NQ_5m.csv")
VOL_DIR = os.path.join(ROOT, "data")
LIT_RUN = "lit_live"
MEMBERS = ("ema_lon_vix", "macd_sweep", "sr_nyreclaim")
CANDIDATES = ("sh_asia", "sh_trend")
BEST = {"ema_lon_vix": "ema_best.json", "macd_sweep": "md_best.json", "sr_nyreclaim": "sr_best.json"}
H1, H2 = ("2026-01-01", "2026-06-30"), ("2026-07-01", "2026-12-31")
LIT_WINDOW = [[120, 930]]
CACHE_S = 20.0
router = APIRouter()
_lock = threading.Lock()
_cache: "collections.OrderedDict" = collections.OrderedDict()


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    """The PC bot (tests replace this function)."""
    from .live import BOT
    return BOT


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def _r(x, nd=2):
    v = _num(x)
    return None if v is None else round(v, nd)


def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def _hm(t):
    return _et(t).strftime("%H:%M") if t else None


def _mins(hm):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(hm or ""))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _hhmm(m):
    m = int(m) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def trading_day(t) -> str:
    e = _et(t)
    d = e.date() + dt.timedelta(days=1) if e.hour >= 18 else e.date()
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d.isoformat()


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:                     # one panel failing never breaks the page
        return {"error": f"{e.__class__.__name__}: {str(e)[:160]}"}


def session_of(mod) -> str | None:
    """engine/lit_learn buckets: London 02:00-05:00, late London 05:00-08:00, New York after 08:00 (minutes after midnight ET)."""
    if mod is None:
        return None
    return "lon_early" if mod < 300 else "lon_late" if mod < 480 else "ny"


SESSION_LABEL = {"lon_early": "London 02:00-05:00 ET", "lon_late": "late London 05:00-08:00 ET", "ny": "New York 08:00-15:30 ET"}


# ================================================================================================ the context
def _stats(rows, key_pnl="pnl", key_r="r", sessions=None) -> dict:
    """n, win %, PF ($), net $, avg R, $ a month (21 sessions a month), trades a week of finished trades."""
    rows = [r for r in rows if _num(r.get(key_r)) is not None]
    n = len(rows)
    pn = [_num(r.get(key_pnl)) or 0.0 for r in rows]
    gp, gl = sum(x for x in pn if x > 0), -sum(x for x in pn if x < 0)
    out = {"n": n, "win": round(100.0 * sum(1 for r in rows if _num(r[key_r]) > 0) / n, 1) if n else None,
           "pf": (round(gp / gl, 2) if gl > 0 else (99.0 if gp > 0 else None)), "net": round(sum(pn), 0),
           "avg_r": round(sum(_num(r[key_r]) for r in rows) / n, 2) if n else None,
           "avg_usd": round(sum(pn) / n, 0) if n else None}
    if sessions:
        out["sessions"] = sessions
        out["per_month"] = round(sum(pn) / (sessions / 21.0), 0)
        out["tpw"] = round(n / (sessions / 5.0), 2)
    return out


def _lit_run():
    d = _read_json(os.path.join(RUNS, LIT_RUN + ".json"))
    if not d:
        return None, [], []
    T = [dict(zip(d["trade_cols"], t)) for t in d.get("trades") or []]
    days = [x[0] for x in d.get("days") or []]
    return d, T, days


def _span_rows(T, days, span):
    a, z = span
    return [t for t in T if a <= t["day"] <= z], len([x for x in days if a <= x <= z]) or None


def load_journal(path=None) -> list:
    out = []
    try:
        with open(path or JOURNAL, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except ValueError:
                        continue
    except OSError:
        pass
    # one record per trade: a PC / cloud record replaces the backtest seed of the same trade
    rank = {"pc": 3, "cloud": 2, "backtest": 1}
    best = {}
    for r in out:
        k = r.get("key") or f"{r.get('day')}|{r.get('entry_t')}|{r.get('dir')}"
        if k not in best or rank.get(r.get("source"), 0) >= rank.get(best[k].get("source"), 0):
            best[k] = r
    return sorted(best.values(), key=lambda r: r.get("entry_t") or 0)


def _replay_brain(day, t):
    from . import brain
    return brain.replay(day, t)


def _bars5(upto=None, n_bytes=1_500_000):
    """The last ~2 months of 5m bars: data/NQ_5m.csv tail (+ the PC's NinjaTrader archive and the bot's own tail)."""
    import io
    import pandas as pd
    if not os.path.exists(BARS_5M):
        return None
    with open(BARS_5M, "rb") as fh:
        head = fh.readline().decode()
        size = os.path.getsize(BARS_5M)
        fh.seek(max(0, size - n_bytes))
        if size > n_bytes:
            fh.readline()
        body = fh.read().decode("utf-8", "replace")
    cols = [c.strip().lower() for c in head.split(",")]
    df = pd.read_csv(io.StringIO(body), header=None, names=cols) if size > n_bytes else pd.read_csv(io.StringIO(head + body))
    df.columns = [c.strip().lower() for c in df.columns]
    if "volume" not in df.columns:
        df["volume"] = 0
    df = df[["time", "open", "high", "low", "close", "volume"]].dropna()
    return df if upto is None else df[df["time"] + 300 <= int(upto)]


def _live_bars(bot, df):
    import pandas as pd
    try:
        from . import pcbars
        arc = pcbars.archive_read(((getattr(bot, "cfg", None) or {}).get("sym") or "NQ"), "5m")
        if arc is not None and len(arc):
            df, _ = pcbars.merge_basis(df, arc)
    except Exception:
        pass
    try:
        tail = list(getattr(bot, "bars_tail", None) or [])
        if tail:
            x = pd.DataFrame(tail)
            if "volume" not in x.columns:
                x["volume"] = 0
            x = x[["time", "open", "high", "low", "close", "volume"]]
            df = x if df is None else pd.concat([df, x]).drop_duplicates("time", keep="last")
    except Exception:
        pass
    return None if df is None else df.sort_values("time").reset_index(drop=True)


def _replay_second(df5, now):
    from . import lit_live, second
    cut = df5[(df5["time"] >= lit_live.window_start(int(now))) & (df5["time"] + 300 <= int(now))]
    cfg = second.load_cfg()
    keep = set(MEMBERS) | set(CANDIDATES)
    cfg = {**cfg, "strategies": {k: v for k, v in (cfg.get("strategies") or {}).items() if k in keep}}
    return second.run(cut.reset_index(drop=True), one_min=None, now=int(now), cfg=cfg, lit=[])


def context(bot, now=None, day=None, hm=None) -> dict:
    """mode "live" (the running bot's Brain / ATLAS run), "replay" (a past session at a minute) or "last" (bot not
    running: the last stored session replayed at its 16:00)."""
    now = int(now or time.time())
    b = getattr(bot, "brain", None) if bot is not None else None
    sec = getattr(bot, "second", None) if bot is not None else None
    ctx = {"now": now, "mode": "live", "brain": None, "second": None, "note": None, "bars": None}
    want_replay = bool(day and re.fullmatch(r"\d{4}-\d{2}-\d{2}", day))
    if b and not want_replay:
        ctx["brain"] = b
        ctx["t"] = int(b.get("t") or now)
    else:
        if want_replay:
            m = _mins(hm) if hm else 16 * 60
            m = 16 * 60 if m is None else m
            d0 = dt.date.fromisoformat(day)
            cal = d0 - dt.timedelta(days=1) if m >= 18 * 60 else d0
            t = int(dt.datetime.combine(cal, dt.time(m // 60, m % 60), ET).timestamp())
            ctx.update(mode="replay", note=f"Replay of {day} at {_hhmm(m)} ET from the stored bars (the same Brain the bot would have built then).")
        else:
            from . import brain
            day = brain.sessions_2026()[0]["day"]
            t = None
            ctx.update(mode="last", note=(f"The bot is not running: this is the last stored session ({day}) replayed at its close. "
                                          "Start the bot (Start page) for the live view."))
        ctx["brain"] = _replay_brain(day, t)
        ctx["t"] = int(ctx["brain"].get("t") or now)
    upto = None if ctx["mode"] == "live" else ctx["t"]
    df = _safe(_bars5, upto)
    if isinstance(df, dict):
        df = None
    if ctx["mode"] == "live":
        df = _live_bars(bot, df)
    ctx["bars"] = df
    if sec and ctx["mode"] == "live":
        ctx["second"] = sec
    elif df is not None and len(df):
        r = _safe(_replay_second, df, ctx["t"])
        ctx["second"] = None if (isinstance(r, dict) and r.get("error") and not r.get("strategies")) else r
    ctx["day"] = (ctx["brain"] or {}).get("day") or trading_day(ctx["t"])
    return ctx


# ================================================================================================ 21 setup radar
def _passed(checks) -> tuple:
    known = [c for c in checks or [] if c.get("ok") is not None]
    return sum(1 for c in known if c.get("ok")), len(checks or [])


def _pts_away(text):
    m = re.search(r"([\d,.]+) pts away", str(text or ""))
    return _num(m.group(1).replace(",", "")) if m else None


def _member_radar(key, s):
    st = s.get("state") or {}
    br = s.get("brain") or {}
    checks = br.get("checks") or []
    ok, n = _passed(checks)
    ff = next((c for c in checks if c.get("ok") is False), None)
    stage = st.get("stage") or br.get("stage")
    return {"key": key, "label": s.get("label"), "short": s.get("short"), "candidate": bool(s.get("candidate")),
            "stage": stage, "text": st.get("text") or br.get("text"), "window": st.get("window"),
            "checks_ok": ok, "checks_n": n, "first_fail": (ff or {}).get("name"), "pts_away": _pts_away(st.get("text")),
            "focus": (br.get("focus") or {}).get("label"), "plan": br.get("plan"),
            "ready": stage in ("armed", "signal", "open", "in_trade")}


def radar(ctx) -> dict:
    b = ctx["brain"] or {}
    st = b.get("stage") or {}
    sides = []
    for w in b.get("watch") or []:
        need = []
        if w.get("stage") == "sweep":
            need.append("a sweep of a LIT level by at least 0.5 ATR")
        if w.get("depth_ok") is False:
            need.append(f"{_r(w.get('need_pts'), 1)} more pts of sweep depth")
        if w.get("idm_ok") is False:
            need.append("an inducement swing taken first")
        if w.get("disp_ok") is False:
            need.append("a displacement candle >= 0.8 ATR")
        if w.get("cisd") is not None and not w.get("cisd_closed"):
            need.append(f"a 5m close through {w['cisd']:,.2f} ({abs(_num(w.get('cisd_dist')) or 0):.1f} pts away)")
        sides.append({"side": w.get("side"), "allowed": w.get("allowed"), "stage": w.get("stage"), "swept": w.get("swept") or [],
                      "depth_atr": w.get("depth_atr"), "disp": w.get("disp"), "cisd": w.get("cisd"), "cisd_dist": w.get("cisd_dist"),
                      "stop_preview": w.get("stop_preview"), "text": w.get("text"), "needs": need})
    lit = {"key": "lit", "label": "Zlarior (LIT)", "stage": st.get("key"), "stage_label": st.get("label"), "stage_n": st.get("n"),
           "stage_of": 10, "text": st.get("waiting"), "price": b.get("price"), "atr": b.get("atr"), "sides": sides,
           "nearest": b.get("nearest") or {}, "at": b.get("at")}
    members = [_member_radar(k, s) for k, s in ((ctx["second"] or {}).get("strategies") or {}).items() if k in MEMBERS + CANDIDATES]
    return {"lit": lit, "atlas": members,
            "summary": _radar_summary(lit, members)}


def _radar_summary(lit, members):
    hot = [m for m in members if m["ready"]]
    s = f"Zlarior: {lit.get('stage_label') or '?'} (step {lit.get('stage_n') or '?'} of 10)."
    if hot:
        s += " ATLAS: " + ", ".join(f"{m['short']} {m['stage']}" for m in hot) + "."
    else:
        s += " No ATLAS member is armed."
    return s


# ================================================================================================ 22 entry windows
def windows_of(text) -> list:
    """[[start_min, end_min], ...] from a window text such as "02:00-05:00, 09:30-11:00 ET" or "Asia 18:00-02:00 ET"."""
    return [[int(a) * 60 + int(b), int(c) * 60 + int(d)] for a, b, c, d in re.findall(r"(\d{2}):(\d{2})-(\d{2}):(\d{2})", str(text or ""))]


def _at(d: dt.date, m: int) -> int:
    return int(dt.datetime.combine(d, dt.time(m // 60, m % 60), ET).timestamp())


def next_window(wins, now: int, skip_monday: bool = False) -> dict | None:
    """The window open at `now` (closes_in) or the next one to open (opens_in), on trading days Mon-Fri (an evening start
    belongs to the next trading day). CME holidays are not counted."""
    if not wins:
        return None
    d0 = _et(now).date()
    spans = []
    for k in range(-2, 10):
        d = d0 + dt.timedelta(days=k)
        if d.weekday() >= 5 or (skip_monday and d.weekday() == 0):
            continue
        for a, z in wins:
            if a >= 18 * 60:                               # starts the evening before trading day d
                prev = d - dt.timedelta(days=1)
                s = _at(prev, a)
                e = _at(prev, z) if z > a else _at(d, z)
            else:
                s, e = _at(d, a), _at(d, z)
            spans.append((s, e))
    spans.sort()
    for s, e in spans:
        if s <= now < e:
            return {"open": True, "start_t": s, "end_t": e, "closes_in_s": e - now, "start_hm": _hm(s), "end_hm": _hm(e)}
    nxt = next(((s, e) for s, e in spans if s > now), None)
    if not nxt:
        return None
    s, e = nxt
    return {"open": False, "start_t": s, "end_t": e, "opens_in_s": s - now, "start_hm": _hm(s), "end_hm": _hm(e),
            "start_day": _et(s).strftime("%a %b %d")}


def windows(ctx) -> dict:
    now = int(time.time()) if ctx["mode"] in ("live", "last") else ctx["t"]
    b = ctx["brain"] or {}
    lw = ((b.get("rules") or {}).get("window")) or LIT_WINDOW
    done = (b.get("stage") or {}).get("key") == "done" and ctx["mode"] != "last"
    rows = [{"key": "lit", "label": "Zlarior (LIT)", "window": ", ".join(f"{_hhmm(a)}-{_hhmm(z)}" for a, z in lw) + " ET",
             "note": "1 trade a day" + ("; today's trade is done" if done else ""), "next": next_window(lw, now)}]
    for k, s in ((ctx["second"] or {}).get("strategies") or {}).items():
        if k not in MEMBERS + CANDIDATES:
            continue
        wt = (s.get("state") or {}).get("window")
        rows.append({"key": k, "label": s.get("label"), "short": s.get("short"), "candidate": bool(s.get("candidate")),
                     "window": wt, "note": "never on a Monday" if k == "ema_lon_vix" else None,
                     "next": next_window(windows_of(wt), now, skip_monday=(k == "ema_lon_vix"))})
    return {"now": now, "rows": rows, "note": "Weekends skipped; CME holidays and early closes are not counted here."}


# ================================================================================================ 23 scorecard
def _band_word(pct, n):
    if not n:
        return "no_trades", "no live trades yet"
    if pct is None:
        return "collecting", "collecting"
    return ("below", "below the expected band") if pct < 10 else ("above", "above the expected band") if pct > 90 else \
        ("on_track", "on track")


def _atlas_live_rows(bot) -> dict:
    """Account B's (ATLAS on its account) closed trades per member: R = $ / (stop pts x micros x $2 + $1.90 a micro)."""
    out = collections.defaultdict(list)
    ab = getattr(bot, "acct_b", None) if bot is not None else None
    if ab is None:
        return out
    prov = getattr(ab, "prov", None) or {}
    for c in list(getattr(ab, "closes", None) or []):
        try:
            pnl, et_ = float(c[2]), int(c[3])
            pv = prov.get(et_) or prov.get(str(et_)) or {}
            q, rp = int(pv.get("qty") or 0), float(pv.get("risk_pts") or 0)
            if q > 0 and rp > 0 and pv.get("key"):
                out[pv["key"]].append({"entry_t": et_, "r": round(pnl / (rp * q * 2.0 + 1.90 * q), 3), "usd": pnl, "exit_kind": "X"})
        except Exception:
            continue
    return out


def _member_research(key) -> dict:
    d = _read_json(os.path.join(SECOND_DIR, BEST.get(key, key + ".json"))) or {}
    T = d.get("trades") or []
    _, _, days = _lit_run()
    out = {}
    for nm, span in (("H1", H1), ("H2", H2)):
        rows = [t for t in T if span[0] <= t.get("day", "") <= span[1]]
        out[nm] = _stats(rows, key_pnl="pnl_usd", sessions=len([x for x in days if span[0] <= x <= span[1]]) or None)
    return out


def scorecard(ctx, bot=None) -> dict:
    from . import ai_watch, second_scorecard as SC
    rows = []
    run, T, days = _lit_run()
    res = {}
    for nm, span in (("H1", H1), ("H2", H2)):
        x, ns = _span_rows(T, days, span)
        res[nm] = _stats(x, sessions=ns)
    J = load_journal()
    live = [r for r in J if r.get("source") == "pc"]
    d = ai_watch.drift_lit(journal_rows=live, now=ctx["now"]) or {}
    lt = _stats([{"r": r.get("r"), "pnl": r.get("pnl")} for r in live])
    word, text = _band_word(d.get("pct"), lt["n"])
    rows.append({"key": "lit", "label": "Zlarior (LIT)", "status": word, "status_text": text, "pct": d.get("pct"),
                 "detail": d.get("text"), "live": lt, "research": res,
                 "band": "run lit_live, 2026 H2 sessions bootstrapped (engine/health_band)"})
    bands = (SC.load() or {}).get("bands") or {}
    live_b = _atlas_live_rows(bot)
    for k in MEMBERS:
        v = SC.verdict(bands.get(k), live_b.get(k) or [])
        kind = v.get("kind")
        word = ("below" if kind == "below" else "above" if (v.get("pct") or 0) > 90 and v.get("n", 0) >= SC.MIN_N else
                "on_track" if kind in ("on_track", "ready") else "collecting" if v.get("n") else "no_trades")
        exp = v.get("expected") or {}
        e20 = (((bands.get(k) or {}).get("expected") or {}).get("by_n") or {}).get(str(SC.READY_N)) or {}
        qi = SC.QS.index
        rows.append({"key": k, "label": _label(ctx, k), "status": word, "status_text": v.get("text"), "pct": v.get("pct"),
                     "live": {"n": v.get("n"), "cum_r": v.get("cum_r"), "usd": v.get("usd"), "win": v.get("win"), "pf": v.get("pf")},
                     "expected_now": exp or None,
                     "expected_20": {"cum_r": [e20["cum_r_q"][qi(p)] for p in (10, 50, 90)], "usd": e20.get("usd"), "win": e20.get("win"),
                                     "pf": e20.get("pf")} if e20.get("cum_r_q") else None,
                     "research": _member_research(k), "band": "2026 H2 trades bootstrapped (engine/second_scorecard)"})
    return {"rows": rows, "rule": SC.RULE,
            "note": "On track = the live result sits between the 10th and 90th percentile of what the backtest expects after the same "
                    "number of sessions / trades. Money is the research's own sizing."}


def _label(ctx, k):
    s = ((ctx["second"] or {}).get("strategies") or {}).get(k) or {}
    return s.get("label") or {"ema_lon_vix": "London EMA trend pullback", "macd_sweep": "MACD divergence at a liquidity sweep",
                              "sr_nyreclaim": "NY sweep-and-reclaim (S/R)"}.get(k, k)


# ================================================================================================ 24 drift
def drift(ctx, bot=None) -> dict:
    from . import ai_watch
    blk = ai_watch.hb_block(bot) if bot is not None else None
    src = "the running bot's AI watch"
    if not blk:
        src = "computed now (bot not running)"
        live = [r for r in load_journal() if r.get("source") == "pc"]
        blk = {"drift": [x for x in (ai_watch.drift_lit(journal_rows=live, now=ctx["now"]),
                                     ai_watch.drift_b(getattr(bot, "acct_b", None) if bot is not None else None),
                                     ai_watch.drift_exec()) if x], "anomalies": [], "loss": None, "switches": None}
    D = blk.get("drift") or []
    worst = "bad" if any(x.get("level") == "bad" for x in D) else "warn" if any(x.get("level") == "warn" for x in D) else \
        "good" if any(x.get("level") == "good" for x in D) else None
    text = {"bad": "Alarm: a strategy is below p5 of its backtest. Check its trades before acting (nothing was changed).",
            "warn": "Watch: a strategy sits at the low end of its expected range (p5-p10).",
            "good": "No drift: every strategy with enough trades is inside its expected range."}.get(
        worst, "Too early to judge: not enough live trades yet (the alarm needs 5+).")
    return {"state": worst or "none", "text": text, "drift": D, "anomalies": (blk.get("anomalies") or [])[-5:],
            "loss": blk.get("loss"), "switches": blk.get("switches"), "source": src,
            "rule": "Below p10 = watch push once a week; below p5 = investigate push. Reports only: it never sizes, pauses or changes a rule."}


# ================================================================================================ 25 grade + 26 similar
MAJOR = re.compile(r"^(PD|PW|PM)[HL]\b|gap|NWOG|NDOG", re.I)


def _focus_setup(b):
    S = b.get("setups") or []
    for status in ("filled", "armed"):
        x = [s for s in S if s.get("status") == status]
        if x:
            return x[-1]
    return S[-1] if S else None


def grade_setup(s, b) -> dict:
    """The trader's grade (research/writeups/lit-trade-selection.md, engine/lit_learn.trader_grade) re-read from the Brain's
    setup card: fresh trap (<= 6 bars), quality liquidity (2+ levels or a day / week / month level or gap), room to run
    (first opposing level >= 1.5R away) and a clean clock (before 08:00 ET, no high-impact news within 60 min)."""
    chk = {c.get("key"): c for c in s.get("checks") or []}
    pts = []
    m = re.search(r"(\d+) bars before the sweep", str((chk.get("idm") or {}).get("text") or ""))
    age = int(m.group(1)) if m else None
    pts.append({"k": "trap", "label": "Fresh trap (inducement <= 6 bars old)", "ok": None if age is None else age <= 6,
                "text": f"inducement {age} bars before the sweep" if age is not None else "no inducement seen"})
    sw = list(s.get("swept") or [])
    major = any(MAJOR.search(x) for x in sw)
    pts.append({"k": "levels", "label": "Quality liquidity (2+ levels or a day/week/month level)", "ok": len(sw) >= 2 or major,
                "text": f"swept {', '.join(sw[:4]) or 'nothing'}"})
    entry, ext, d = _num(s.get("cisd")), _num(s.get("ext")), int(s.get("dir") or 0)
    room = None
    if entry is not None and ext is not None and d:
        risk = abs(entry - ext) + 0.25
        opp = [_num(l.get("price")) for l in b.get("levels") or [] if l.get("side") == ("H" if d > 0 else "L") and _num(l.get("price")) is not None]
        opp = [p for p in opp if (p - entry) * d > 0]
        first = min(opp, key=lambda p: abs(p - entry)) if opp else None
        room = None if first is None else round(abs(first - entry) / risk, 2)
        pts.append({"k": "room", "label": "Room to run (first opposing level >= 1.5R away)", "ok": True if first is None else room >= 1.5,
                    "text": "no opposing level in the way" if first is None else f"first opposing level {first:,.2f} = {room}R away"})
    else:
        pts.append({"k": "room", "label": "Room to run (first opposing level >= 1.5R away)", "ok": None, "text": "no entry / stop yet"})
    mod = _mins(s.get("hm"))
    news = [_mins(n.get("time")) for n in ((b.get("guards") or {}).get("news") or []) if _mins(n.get("time")) is not None]
    near = [n for n in news if mod is not None and 0 <= n - mod <= 60]
    pts.append({"k": "clock", "label": "Clean clock (before 08:00 ET, no big news in the next 60 min)",
                "ok": None if mod is None else (mod < 480 and not near),
                "text": f"setup at {s.get('hm')} ET" + (f", news at {_hhmm(near[0])}" if near else "")})
    score = sum(1 for p in pts if p["ok"])
    g = "A" if score >= 4 else "B" if score >= 2 else "C"
    return {"grade": g, "points": score, "of": 4, "detail": pts, "session": session_of(mod), "dir": d,
            "rules_ok": _passed(s.get("checks"))[0], "rules_n": len(s.get("checks") or [])}


def grade(ctx) -> dict:
    b = ctx["brain"] or {}
    s = _focus_setup(b)
    J = load_journal()
    last = J[-1] if J else None
    out = {"setup": None, "last_trade": None}
    if s:
        g = grade_setup(s, b)
        out["setup"] = {"hm": s.get("hm"), "side": s.get("side"), "status": s.get("status"), "status_text": s.get("status_text"),
                        "swept": s.get("swept"), "day": b.get("day"), **g, "source": "estimate from the Brain's setup card"}
        ent = [r for r in J if r.get("day") == b.get("day") and int(r.get("dir") or 0) == int(s.get("dir") or 0)]
        if s.get("status") == "filled" and ent and ent[-1].get("grade"):
            out["setup"].update(grade=ent[-1]["grade"], source="the LIT journal (the trade's own features)")
    if last:
        out["last_trade"] = {"day": last.get("day"), "side": last.get("side"), "exit": last.get("exit"), "r": last.get("r"),
                             "pnl": last.get("pnl"), "grade": last.get("grade"), "buckets": last.get("buckets") or {},
                             "cause": last.get("cause"), "source": last.get("source"),
                             "session": (last.get("buckets") or {}).get("session")}
    focus = out["setup"] or out["last_trade"] or {}
    out["confidence"] = _confidence(focus.get("grade"))
    out["text"] = (f"{'Current' if out['setup'] else 'Last'} setup: grade {focus.get('grade') or '?'}"
                   + (f" ({out['setup']['points']} of 4 points)" if out["setup"] else "") + ". " + (out["confidence"] or {}).get("text", ""))
    return out


def _confidence(g):
    if not g:
        return None
    rows = [r for r in load_journal() if r.get("grade") == g and str(r.get("day", "")) >= "2026-01-01"]
    st = _stats(rows)
    if not st["n"]:
        return {"grade": g, "text": f"No 2026 trade of grade {g} in the journal yet."}
    lvl = "high" if (st["avg_r"] or 0) >= 1.0 else "medium" if (st["avg_r"] or 0) >= 0.3 else "low"
    return {"grade": g, "level": lvl, **st,
            "text": f"Grade {g} in 2026: {st['n']} trades, {st['win']:.0f}% winners, {st['avg_r']:+.2f}R a trade on average ({lvl} confidence)."}


def similar(ctx, gr=None) -> dict:
    gr = gr if isinstance(gr, dict) and not gr.get("error") else grade(ctx)
    f = gr.get("setup") or gr.get("last_trade") or {}
    g, sess = f.get("grade"), f.get("session") or (f.get("buckets") or {}).get("session")
    cause = (gr.get("last_trade") or {}).get("cause") if not gr.get("setup") else None
    J = [r for r in load_journal() if str(r.get("day", "")) >= "2026-01-01"]
    out = {"grade": g, "session": sess, "session_label": SESSION_LABEL.get(sess), "groups": []}
    if J:
        def grp(name, rows):
            st = _stats([{"r": r.get("r"), "pnl": r.get("pnl")} for r in rows])
            return {"name": name, **st, "trades": [{"day": r.get("day"), "side": r.get("side"), "exit": r.get("exit"), "r": _r(r.get("r")),
                                                    "pnl": _r(r.get("pnl"), 0), "grade": r.get("grade"),
                                                    "session": (r.get("buckets") or {}).get("session"), "cause": r.get("cause")}
                                                   for r in rows[-8:][::-1]]}
        if g and sess:
            out["groups"].append(grp(f"Grade {g}, {SESSION_LABEL.get(sess, sess)}",
                                     [r for r in J if r.get("grade") == g and (r.get("buckets") or {}).get("session") == sess]))
        if g:
            out["groups"].append(grp(f"Every grade {g} trade", [r for r in J if r.get("grade") == g]))
        if cause:
            out["groups"].append(grp(f"Same loss cause ({cause})", [r for r in J if r.get("cause") == cause]))
        out["groups"].append(grp("Every 2026 trade (baseline)", J))
        out["source"] = "LIT journal (data/lit_journal.jsonl): 2026 backtest seed + routed trades"
    else:
        _, T, days = _lit_run()
        T = [t for t in T if t["day"] >= "2026-01-01"]
        same = [t for t in T if sess and session_of(_et(t["entry_t"]).hour * 60 + _et(t["entry_t"]).minute) == sess]
        for name, rows in ((f"Same session ({SESSION_LABEL.get(sess, sess)})", same), ("Every 2026 trade (baseline)", T)):
            if rows:
                st = _stats(rows)
                out["groups"].append({"name": name, **st, "trades": [{"day": t["day"], "side": "LONG" if t["dir"] > 0 else "SHORT",
                                                                      "exit": t["exit"], "r": _r(t["r"]), "pnl": _r(t["pnl"], 0)}
                                                                     for t in rows[-8:][::-1]]})
        out["source"] = "run lit_live (no journal on this PC)"
    top = out["groups"][0] if out["groups"] else None
    out["text"] = (f"{top['name']}: {top['n']} trades in 2026, {top['win']:.0f}% won, {top['avg_r']:+.2f}R and "
                   f"${top['avg_usd']:+,.0f} a trade on average." if top and top.get("n") else "No similar 2026 trade found.")
    return out


# ================================================================================================ 27 regime
def _ema(vals, n):
    k, e = 2.0 / (n + 1), None
    for v in vals:
        e = v if e is None else e + k * (v - e)
    return e


def trend_of(df, secs) -> dict | None:
    if df is None or not len(df):
        return None
    g = df.assign(b=(df["time"] // secs) * secs).groupby("b")["close"].last()
    if len(g) < 60:
        return None
    c = list(g.values)
    e21, e50 = _ema(c, 21), _ema(c, 50)
    d = "up" if e21 > e50 else "down" if e21 < e50 else "flat"
    return {"dir": d, "ema21": round(e21, 2), "ema50": round(e50, 2), "close": round(c[-1], 2), "gap_pts": round(e21 - e50, 2)}


def _vol_file(name):
    import pandas as pd
    p = os.path.join(VOL_DIR, f"{name}_1d.csv")
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df.dropna(subset=["close"])
    return _r(df["close"].iloc[-1]) if len(df) else None


def _ranges(df, day):
    """Asia (18:00-02:00 ET) and London (02:00-05:00 ET) high / low / range of trading day `day` + the 20-session average."""
    if df is None or not len(df):
        return []
    import pandas as pd
    e = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(ET)
    mod = e.dt.hour * 60 + e.dt.minute
    td = (e + pd.to_timedelta((e.dt.hour >= 18).astype(int), unit="D")).dt.strftime("%Y-%m-%d")
    x = df.assign(mod=mod.values, td=td.values)
    out = []
    for name, sel in (("Asia", lambda m: (m >= 1080) | (m < 120)), ("London", lambda m: (m >= 120) & (m < 300))):
        s = x[sel(x["mod"])]
        g = s.groupby("td").agg(h=("high", "max"), l=("low", "min"))
        g["rng"] = g["h"] - g["l"]
        prev = g[g.index < day].tail(20)
        row = g.loc[day] if day in g.index else None
        out.append({"name": name, "high": _r(row["h"]) if row is not None else None, "low": _r(row["l"]) if row is not None else None,
                    "range": _r(row["rng"], 1) if row is not None else None, "avg20": _r(prev["rng"].mean(), 1) if len(prev) else None,
                    "window": "18:00-02:00 ET" if name == "Asia" else "02:00-05:00 ET"})
    for r in out:
        r["pct_avg"] = round(100 * r["range"] / r["avg20"]) if r.get("range") and r.get("avg20") else None
    return out


def _news_next(now):
    from . import calendar_week as cw
    d = _et(now).date()
    rows = cw.dashboard_rows(d, d + dt.timedelta(days=7), "high", use_feed=False)
    nxt = next((r for r in rows if int(r.get("t") or 0) > now), None)
    today = [{"time": r.get("time_et"), "event": r.get("event")} for r in rows if r.get("date") == d.isoformat()]
    return {"next": {"event": nxt.get("event"), "t": nxt.get("t"), "date": nxt.get("date"), "time": nxt.get("time_et"),
                     "in_s": int(nxt["t"]) - now, "weekday": nxt.get("weekday")} if nxt else None, "today": today}


def regime(ctx) -> dict:
    b = ctx["brain"] or {}
    g = (b.get("guards") or {}).get("vix") or {}
    vix, vxn = _num(g.get("vix")), _num(g.get("vxn"))
    if vix is None:
        vix = _safe(_vol_file, "VIX")
        vix = vix if not isinstance(vix, dict) else None
    if vxn is None:
        vxn = _safe(_vol_file, "VXN")
        vxn = vxn if not isinstance(vxn, dict) else None
    vb = "low" if vix is not None and vix < 16 else "mid" if vix is not None and vix < 22 else "high" if vix is not None else None
    df = ctx.get("bars")
    ema = ((ctx["second"] or {}).get("strategies") or {}).get("ema_lon_vix", {}).get("state") or {}
    t15, t60 = _safe(trend_of, df, 900), _safe(trend_of, df, 3600)
    t15 = None if isinstance(t15, dict) and t15.get("error") else t15
    t60 = None if isinstance(t60, dict) and t60.get("error") else t60
    if ema.get("t15") in (1, -1) and t15:
        t15["dir"] = "up" if ema["t15"] > 0 else "down"
    if ema.get("t60") in (1, -1) and t60:
        t60["dir"] = "up" if ema["t60"] > 0 else "down"
    now = int(time.time()) if ctx["mode"] in ("live", "last") else ctx["t"]
    news = _safe(_news_next, now)
    rng = _safe(_ranges, df, ctx["day"])
    trend = "up" if (t15 or {}).get("dir") == "up" and (t60 or {}).get("dir") == "up" else \
        "down" if (t15 or {}).get("dir") == "down" and (t60 or {}).get("dir") == "down" else "mixed"
    words = {"low": "calm (VIX under 16)", "mid": "normal (VIX 16-22)", "high": "nervous (VIX 22+)"}
    text = (f"Market {words.get(vb, 'VIX unknown')}; trend {trend} on 15m and 1h"
            + (f"; next big news {news['next']['event']} {news['next']['weekday']} {news['next']['time']} ET." if isinstance(news, dict) and news.get("next") else "."))
    return {"vix": vix, "vxn": vxn, "vix_band": vb, "move": _r(g.get("move")), "open18": _r(g.get("open18")), "up": _r(g.get("up")),
            "dn": _r(g.get("dn")), "atr5": b.get("atr"), "price": b.get("price"), "t15": t15, "t60": t60, "trend": trend,
            "news": news, "ranges": rng if isinstance(rng, list) else [], "text": text}


# ================================================================================================ 28 levels
def levels(ctx) -> dict:
    b = ctx["brain"] or {}
    L = b.get("levels") or []
    swept = sorted([l for l in L if l.get("taken")], key=lambda l: _mins(l.get("taken_hm")) if _mins(l.get("taken_hm")) is not None else 9999)
    open_ = sorted([l for l in L if not l.get("taken")], key=lambda l: abs(_num(l.get("dist")) or 1e9))
    f = lambda l: {k: l.get(k) for k in ("label", "price", "side", "kind", "kind_label", "dist", "dist_atr", "taken_hm", "depth_atr", "also")}
    deep = [l for l in swept if (_num(l.get("depth_atr")) or 0) >= 0.5]
    return {"price": b.get("price"), "atr": b.get("atr"), "day": b.get("day"), "swept": [f(l) for l in swept],
            "untouched": [f(l) for l in open_], "n": len(L),
            "text": f"{len(swept)} of {len(L)} levels swept today ({len(deep)} deep enough for LIT, >= 0.5 ATR); "
                    f"{len(open_)} untouched, the nearest {open_[0]['label']} {abs(_num(open_[0].get('dist')) or 0):,.0f} pts away."
            if open_ else f"{len(swept)} of {len(L)} levels swept today."}


# ================================================================================================ 29 ATLAS members
def atlas(ctx) -> dict:
    S = (ctx["second"] or {}).get("strategies") or {}
    day = ctx["day"]
    rows = []
    for k in MEMBERS + CANDIDATES:
        s = S.get(k)
        if not s:
            continue
        T = [t for t in s.get("trades") or [] if t.get("entry_t")]
        fin = [t for t in T if t.get("exit_kind") not in (None, "OPEN", "")]
        today = [t for t in T if t.get("day") == day]
        last = fin[-1] if fin else None
        st = s.get("state") or {}
        rows.append({"key": k, "label": s.get("label"), "short": s.get("short"), "candidate": bool(s.get("candidate")),
                     "route_label": s.get("route_label") or ("ROUTED" if s.get("route") else "paper"), "stage": st.get("stage"),
                     "text": st.get("text"), "window": st.get("window"),
                     "today": [{"hm": _hm(t["entry_t"]), "side": "long" if (t.get("dir") or 0) > 0 else "short", "exit_kind": t.get("exit_kind"),
                                "r": _r(t.get("r")), "usd": _r(t.get("usd"), 0)} for t in today],
                     "last": {"day": last.get("day"), "side": "long" if (last.get("dir") or 0) > 0 else "short", "exit_kind": last.get("exit_kind"),
                              "r": _r(last.get("r")), "usd": _r(last.get("usd"), 0)} if last else None,
                     "research": _member_research(k) if k in MEMBERS else None, "error": s.get("error")})
    on = sum(1 for r in rows if r["stage"] in ("armed", "signal", "open"))
    return {"rows": rows, "day": day, "text": f"{len(rows)} strategies watched; {on} armed or in a trade now." if rows else
            "ATLAS has not run yet (it runs after each LIT poll while the bot runs)."}


# ================================================================================================ 30 strategy 3 (scalp research)
def _front_matter(path) -> dict:
    with open(path, encoding="utf-8") as fh:
        txt = fh.read(20000)
    m = re.match(r"---\s*\n(.*?)\n---", txt, re.S)
    out = {}
    for ln in (m.group(1).splitlines() if m else []):
        if ":" in ln:
            k, v = ln.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def strategy3(ctx=None) -> dict:
    docs = []
    for p in sorted(glob.glob(os.path.join(WRITEUPS, "scalp-*.md")))[-6:]:
        fm = _front_matter(p)
        docs.append({"file": os.path.relpath(p, ROOT).replace(os.sep, "/"), "title": fm.get("title") or os.path.basename(p),
                     "status": fm.get("status"), "date": fm.get("date"), "summary": (fm.get("summary") or "")[:600]})
    data = []
    for p in sorted(glob.glob(os.path.join(SCALP_DIR, "*.json")))[-6:]:
        d = _read_json(p) or {}
        if not isinstance(d, dict):
            continue
        keep = {k: d.get(k) for k in ("id", "title", "status", "verdict", "built") if d.get(k) is not None}
        nums = d.get("numbers") or d.get("spans") or {}
        if isinstance(nums, dict):
            keep["numbers"] = {k: {kk: v.get(kk) for kk in ("n", "tpw", "win", "pf", "net", "per_month", "dd") if isinstance(v, dict) and v.get(kk) is not None}
                               for k, v in list(nums.items())[:4] if isinstance(v, dict)}
        data.append({"file": os.path.relpath(p, ROOT).replace(os.sep, "/"), **keep})
    status = (docs[-1].get("status") if docs else None) or (data[-1].get("status") if data else None) or "in research"
    return {"name": "Strategy 3 (scalp)", "status": status, "writeups": docs, "data": data, "paper_only": True,
            "text": ("Scalp research: " + status + ". Paper only; it trades nothing until the research proves it in 2026 and 2021-25.")
            if docs or data else "Strategy 3 (scalp) is in research: no write-up or result file yet. Nothing trades."}


# ================================================================================================ the page
def build(bot, now=None, day=None, hm=None) -> dict:
    t0 = time.time()
    ctx = context(bot, now=now, day=day, hm=hm)
    gr = _safe(grade, ctx)
    out = {"v": 1, "t": int(time.time()), "mode": ctx["mode"], "note": ctx["note"], "day": ctx["day"], "at": (ctx["brain"] or {}).get("at"),
           "brain_t": ctx["t"], "running": bool(getattr(bot, "running", False)) if bot is not None else False,
           "radar": _safe(radar, ctx), "windows": _safe(windows, ctx), "scorecard": _safe(scorecard, ctx, bot),
           "drift": _safe(drift, ctx, bot), "grade": gr, "similar": _safe(similar, ctx, gr), "regime": _safe(regime, ctx),
           "levels": _safe(levels, ctx), "atlas": _safe(atlas, ctx), "strategy3": _safe(strategy3, ctx),
           "paper_only": True, "read_only": True}
    out["build_ms"] = int((time.time() - t0) * 1000)
    return out


@router.get("/api/next/insight")
def r_insight(day: str = "", hm: str = ""):
    try:
        bot = _bot()
    except Exception:
        bot = None
    live = bool(getattr(bot, "brain", None))
    # live: rebuilt every CACHE_S; the replayed last session only changes with the stored bars (10 minutes); a replay never
    key = (day, hm, live, int(time.time() // CACHE_S) if live else int(time.time() // 600) if not day else 0)
    try:
        with _lock:
            if key in _cache:
                return _J(_cache[key])
        v = build(bot, day=day or None, hm=hm or None)
        with _lock:
            _cache[key] = v
            while len(_cache) > 12:
                _cache.popitem(last=False)
        return _J(v)
    except Exception as e:                       # never 500 the dashboard over a page
        return _J({"error": f"{e.__class__.__name__}: {str(e)[:200]}"}, 500)
