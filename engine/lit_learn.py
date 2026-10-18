"""LIT learning loop (owner, 2026-10-18: "It should start learning from its losses and change. This is a must.").

A loop that is real but cannot overfit or blow up the eval:

1. Journal (data/lit_journal.jsonl, append-only, one JSON object per line). Every finished LIT trade - the backtest seed, the
   cloud paper ledger (tools/cloud_monitor.py, kept on the dashboard branch) and the PC / NinjaTrader bot (engine/live.py,
   routed trades) - gets one record: the 50 causal features at entry (tools/lit_select.py feats, plus the 4H draw / 4H
   candle and the trader's A/B/C grade), the outcome (exit, R, $), MFE / MAE, hindsight facts and a loss cause code.
2. Causes (cause_codes): rules written from research/writeups/lit-losses.md. One primary code per loss and every matching
   tag: news_spike, wick_then_target, es_no_confirm, against_4h_draw, late_london, opp_extreme_in, stale_trap, wide_stop,
   not_turning_point (every stop-out), be_scratch, eod_fade. They explain; they never size anything.
3. Learner (review, every Sunday): from the journal's trailing 6 months it re-estimates BOUNDED knobs only: a size multiplier
   per feature bucket (fresh trap, levels swept, session, VIX regime, the A/B/C grade, ES confirmation, 4H draw) between
   0.5x and 1.25x, and a skip switch for a bucket only if it lost money with >= 15 trades. Estimate = the bucket's mean R
   shrunk toward the overall mean with a prior worth 20 trades (Bayesian shrinkage toward 1.0x), as a ratio to the overall
   mean R. It never touches stops, targets, entries or the LIT rules.
4. Guardrails (every proposal, before it goes live):
   a. walk-forward: the same learning rule, run at the start of each of the last six 30-day blocks on the data before it,
      must have made money on the blocks it changed (>= 2 of them), AND the change must make money in both halves of the
      visible 2026 history (H1 Jan-Jun / H2 Jul-on once each half has 20+ trades; before that the visible data cut in two);
   b. trades a week stay 2-4 (only a skip can lower them);
   c. the MFFU 50K 2-week fail rate (fresh eval on every session, eval sizing with the 60% room cap) does not go up, on the
      trailing 6 months and on the whole visible history;
   d. at most one bucket changes per week, by at most 0.25x;
   e. signal: a move away from 1.0x (or a skip) needs the bucket's mean R to differ from the rest of the 6-month window by
      Z_MIN standard errors (pooled spread, R winsorized at +/-5R, 10+ trades on each side). Calibrated on pure-noise journals (tests/test_lit_learn.py), not
      on 2026. Moves back toward 1.0x need no signal.
   Otherwise the knob stays. Every decision (also "no change") is written to data/lit_learning.json with the reason, the
   evidence and the before/after numbers, and can be reverted (revert()).
5. Modes: "observe" logs proposals and keeps a shadow knob set (what the bot would size), applies nothing (multiplier 1.0);
   "apply" multiplies the size (engine/sizing.py lit_qty, one rounding, a size-up never risks more than $900). The mode is
   in data/lit_learning.json; the history replay (tools/lit_learn_replay.py) decides which one ships.

    python -m engine.lit_learn status             # mode, knobs, last review, loss causes this month
    python -m engine.lit_learn review [--asof YYYY-MM-DD] [--journal P] [--learning P]
    python -m engine.lit_learn revert <decision id>
    python -m engine.lit_learn mode observe|apply
    python -m engine.lit_learn pull               # the cloud's copy (dashboard branch) -> data/lit_learning.json
    python -m engine.lit_learn selftest
Paper only.
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import math
import os
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
JOURNAL_PATH = os.path.join(DATA, "lit_journal.jsonl")
LEARNING_PATH = os.path.join(DATA, "lit_learning.json")
ET = ZoneInfo("America/New_York")

VERSION = 1
PRIOR_N = 20.0             # the prior is worth 20 trades at the overall mean R
MULT_LO, MULT_HI = 0.5, 1.25
STEP_MAX = 0.25            # max change of one knob per review
STEP = 0.05                # knobs move on a 0.05 grid
SKIP_MIN_N = 15            # a skip needs >= 15 trades in the bucket that lost money
WINDOW_DAYS = 182          # trailing 6 months: estimation window and the guardrails' recent window
WF_BLOCKS, WF_BLOCK_DAYS, WF_MIN_ACTIVE = 6, 30, 2
Z_MIN = 2.5                # significance gate: a move away from 1.0x (or a skip) needs the bucket's mean R to differ from the
                           # rest of the window by >= Z_MIN standard errors (pooled spread, R winsorized at +/-WINSOR). Set on
                           # pure-noise journals only: 2.0 -> a false change in 15% of weeks, 2.5 -> 4%, 3.0 -> 1%
WINSOR = 5.0
SIG_MIN_N = 10           # the signal test needs 10+ trades in the bucket and 10+ outside it
ACTIVE = None              # families the learner may move (None = all of FAMILIES; the sensitivity study narrows it)
HISTORY_DAYS = 364         # the visible history of a review: the trailing 12 months (2026: everything from Jan 2)
MIN_TRADES = 20            # no review below this many journal trades in the window
TPW = (2.0, 4.0)
RISK_CAP = 900.0           # a sized-up trade never risks more than this (MFFU $1,000 soft daily loss limit)
PV, COMM, SLIP = 2.0, 1.40, 0.25
EVAL = {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 50100.0, "room_k": 0.6, "usd": 800.0, "ref": 25.0}
SOURCE_RANK = {"pc": 3, "cloud": 2, "backtest": 1}

# ------------------------------------------------------------------------------------------------ buckets
FAMILIES = collections.OrderedDict([
    ("trap", ("Inducement (trap) age", {"fresh": "fresh trap (inducement <= 6 bars / 30 min old)", "stale": "older trap (> 6 bars)"})),
    ("levels", ("Liquidity taken", {"multi": "2+ levels or a daily/weekly/monthly level or gap", "single": "one minor level"})),
    ("session", ("Entry time", {"lon_early": "London 02:00-05:00 ET", "lon_late": "late London 05:00-08:00 ET",
                                "ny": "New York 08:00-15:30 ET"})),
    ("vix", ("VIX regime", {"low": "VIX under 16", "mid": "VIX 16-22", "high": "VIX 22+"})),
    ("grade", ("Trader's grade", {"A": "grade A (4 of 4 points)", "B": "grade B (2-3 points)", "C": "grade C (0-1 points)"})),
    ("es", ("ES confirmation", {"confirm": "ES swept its own level too", "no_confirm": "ES did not sweep"})),
    ("h4", ("4H draw", {"with": "nearest untaken 4H swing on the target side", "against": "nearest untaken 4H swing on the stop side",
                        "none": "no untaken 4H swing nearby"})),
])


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def trader_grade(f: dict) -> str | None:
    """The trader's grade of research/writeups/lit-trade-selection.md (= tools/lit_select_rules.trader_grade): 1 point each
    for a fresh trap (<= 6 bars), quality liquidity (2+ levels or a daily/weekly/monthly level or gap), room to run (first
    opposing level >= 1.5R away) and a clean clock (London morning, no high-impact release in the next 60 min). A 4, B 2-3, C 0-1."""
    need = ("idm_age", "n_swept", "major", "obst_r", "news_next", "mod")
    if any(_num(f.get(k)) is None for k in need):
        return None
    p = int(f["idm_age"] <= 6) + int(f["n_swept"] >= 2 or f["major"] == 1) + int(f["obst_r"] >= 1.5) + \
        int(f["news_next"] > 60 and f["mod"] < 480)
    return "A" if p >= 4 else "B" if p >= 2 else "C"


def buckets(f: dict | None) -> dict:
    """{family: bucket or None} of one trade's features (None = unknown: that family's knob does not apply)."""
    f = f or {}
    out = {k: None for k in FAMILIES}
    a = _num(f.get("idm_age"))
    if a is not None:
        out["trap"] = "fresh" if a <= 6 else "stale"
    n, mj = _num(f.get("n_swept")), _num(f.get("major"))
    if n is not None and mj is not None:
        out["levels"] = "multi" if (n >= 2 or mj == 1) else "single"
    m = _num(f.get("mod"))
    if m is not None:
        out["session"] = "lon_early" if m < 300 else "lon_late" if m < 480 else "ny"
    v = _num(f.get("vix"))
    if v is not None:
        out["vix"] = "low" if v < 16 else "mid" if v < 22 else "high"
    out["grade"] = trader_grade(f)
    e = _num(f.get("es_swept"))
    if e is not None:
        out["es"] = "confirm" if e >= 0.5 else "no_confirm"
    h = _num(f.get("h4_draw"))
    if h is not None:
        out["h4"] = "with" if h > 0 else "against" if h < 0 else "none"
    return out


def bucket_label(fam, b):
    return f"{FAMILIES[fam][0]}: {FAMILIES[fam][1].get(b, b)}"


# ------------------------------------------------------------------------------------------------ 4H draw (causal, bars <= i)
def _h4(M):
    c = getattr(M, "_learn_h4", None)
    if c is not None:
        return c
    import numpy as np
    rel = (M.mod - 1080) % 1440
    g = M.day_of.astype(np.int64) * 10 + rel // 240
    starts = np.r_[0, np.flatnonzero(np.diff(g)) + 1]
    ends = np.r_[starts[1:], M.n]
    H = np.maximum.reduceat(M.h, starts)
    L = np.minimum.reduceat(M.l, starts)
    O = M.o[starts]
    C = M.c[ends - 1]
    cid = np.repeat(np.arange(len(starts)), ends - starts)
    c = (starts, ends, H, L, O, C, cid)
    M._learn_h4 = c
    return c


def h4_feats(M, i: int, d: int, lookback: int = 30) -> dict:
    """At the close of 5m bar i, for a trade in direction d: h4_candle (+1 the last closed 4H candle closed the trade's way,
    -1 against, 0 doji) and h4_draw (+1 the nearest untaken 4H swing is on the target side, -1 on the stop side, 0 none in
    the last `lookback` 4H candles). 4H candles aligned to 18:00 ET (18, 22, 02, 06, 10, 14). Uses bars <= i only."""
    starts, ends, H, L, O, C, cid = _h4(M)
    j = int(cid[i])
    if j < 3:
        return {"h4_candle": float("nan"), "h4_draw": float("nan")}
    cd = C[j - 1] - O[j - 1]
    out = {"h4_candle": float((1 if cd > 0 else -1 if cd < 0 else 0) * d)}
    px = float(M.c[i])
    best = None
    for m in range(max(1, j - lookback), j - 1):         # swing m is confirmed by the closed candle m + 1 <= j - 1
        if H[m] > H[m - 1] and H[m] > H[m + 1] and float(M.h[ends[m]:i + 1].max()) <= H[m]:
            dist = abs(float(H[m]) - px)
            if best is None or dist < best[0]:
                best = (dist, 1)
        if L[m] < L[m - 1] and L[m] < L[m + 1] and float(M.l[ends[m]:i + 1].min()) >= L[m]:
            dist = abs(float(L[m]) - px)
            if best is None or dist < best[0]:
                best = (dist, -1)
    out["h4_draw"] = 0.0 if best is None else float(best[1] * d)
    return out


# ------------------------------------------------------------------------------------------------ news calendar
_NEWS = {}


def news_minutes(day: str) -> list:
    """ET minutes of the scheduled high-impact releases on `day` (data/news/events.csv)."""
    if "cal" not in _NEWS:
        cal = collections.defaultdict(list)
        p = os.path.join(DATA, "news", "events.csv")
        try:
            import csv
            with open(p, encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    if r.get("impact") != "high":
                        continue
                    tm = str(r.get("time_et") or "")
                    hh, mm = (int(x) for x in tm.split(":")[:2]) if ":" in tm else (8, 30)
                    cal[r["date"]].append(hh * 60 + mm)
        except Exception:
            pass
        _NEWS["cal"] = cal
    return _NEWS["cal"].get(day, [])


def _mod(t):
    e = dt.datetime.fromtimestamp(int(t), ET)
    return e.hour * 60 + e.minute


# ------------------------------------------------------------------------------------------------ hindsight facts
def post_facts(M, t: dict) -> dict:
    """What the rest of the day did (hindsight, for the cause codes only; never a sizing input). t: dir, entry_t, exit_t,
    target_px (price), day. target_after_stop: price reached the target after the exit, before the 15:55 flat;
    opp_ext_in: the day's target-side extreme made before the entry was never exceeded afterwards; news_in_trade: a
    high-impact release from 15 min before the entry to the exit; complete: the bars reach the 15:55 flat."""
    import numpy as np
    d = int(t["dir"])
    out = {"target_after_stop": None, "opp_ext_in": None, "news_in_trade": None, "complete": False}
    try:
        ei = int(np.searchsorted(M.t, int(t["entry_t"]), side="right") - 1)
        xi = int(np.searchsorted(M.t, int(t["exit_t"]) - 1, side="right") - 1)
        k = int(M.day_of[ei])
        s, e = M.days[k][1], M.days[k][2]
        fl = [j for j in range(ei, e) if M.mod[j] < 955]
        last = fl[-1] if fl else ei
        out["complete"] = bool(e < M.n or M.mod[M.n - 1] >= 950)
        tg = t.get("target_px")
        if tg is not None and xi + 1 <= last:
            seg = slice(xi + 1, last + 1)
            out["target_after_stop"] = bool(M.h[seg].max() >= float(tg)) if d == 1 else bool(M.l[seg].min() <= float(tg))
        if ei > s:
            if d == 1:
                out["opp_ext_in"] = bool(float(M.h[s:ei].max()) >= float(M.h[ei:last + 1].max()))
            else:
                out["opp_ext_in"] = bool(float(M.l[s:ei].min()) <= float(M.l[ei:last + 1].min()))
    except Exception:
        pass
    try:
        a, z = _mod(t["entry_t"]), _mod(t["exit_t"])
        out["news_in_trade"] = any(a - 15 <= m <= z for m in news_minutes(str(t["day"])))
    except Exception:
        pass
    return out


# ------------------------------------------------------------------------------------------------ cause codes
CAUSES = collections.OrderedDict([
    ("news_spike", "news spike: a high-impact release hit the trade (15 min before the entry to the exit)"),
    ("wick_then_target", "stopped by a wick, then price went on to the target the same day"),
    ("opp_extreme_in", "the day's opposite extreme was already in before the entry"),
    ("es_no_confirm", "ES did not confirm: ES did not sweep its own level"),
    ("stale_trap", "stale trap: the inducement swing was older than 10 bars (50 min)"),
    ("late_london", "late in the London move: entry 05:00-08:00 ET"),
    ("wide_stop", "wide stop: planned stop over 47 pts"),
    ("against_4h_draw", "against the 4H draw: the nearest untaken 4H swing was on the stop side"),
    ("not_turning_point", "not the day's turning point: price ran through the sweep extreme"),
    ("be_scratch", "breakeven scratch: went +1R, came back to the entry"),
    ("eod_fade", "flat at 15:55 with a loss"),
])


def cause_codes(rec: dict):
    """(primary cause or None for a winner, [every matching tag]). Rules from lit-losses.md: a stop-out always means the
    sweep was not the day's turning point (the stop sits 1 tick beyond the sweep extreme); the more specific setup or
    hindsight reason, when one matches, is the primary code."""
    ex = str(rec.get("exit") or "")
    r = _num(rec.get("r")) or 0.0
    if ex in ("TARGET",) or (ex not in ("BE",) and r > 0.05):
        return None, []
    f = rec.get("f") or {}
    p = rec.get("post") or {}
    tags = []
    stop = ex in ("STOP", "DLL")
    if p.get("news_in_trade"):
        tags.append("news_spike")
    if stop and p.get("target_after_stop"):
        tags.append("wick_then_target")
    if p.get("opp_ext_in"):
        tags.append("opp_extreme_in")
    if _num(f.get("es_swept")) == 0:
        tags.append("es_no_confirm")
    if (_num(f.get("idm_age")) or 0) > 10:
        tags.append("stale_trap")
    m = _num(f.get("mod"))
    if m is not None and 300 <= m < 480:
        tags.append("late_london")
    sp = _num(f.get("stop_pts")) or _num(rec.get("risk_pts")) or 0
    if sp > 47:
        tags.append("wide_stop")
    if (_num(f.get("h4_draw")) or 0) < 0:
        tags.append("against_4h_draw")
    if stop:
        tags.append("not_turning_point")
    if ex == "BE":
        return "be_scratch", tags + ["be_scratch"]
    if not stop:                                       # EOD / TIME with a loss
        return (tags[0] if tags else "eod_fade"), tags + ([] if tags else ["eod_fade"])
    return tags[0], tags


# ------------------------------------------------------------------------------------------------ journal records
def qty_for(risk_pts, usd=800.0, ref=20.0, max_micros=40):
    r = usd if risk_pts <= ref else usd * ref / risk_pts
    return max(0, min(max_micros, int(r / (risk_pts * PV))))


def q_pre_of(risk_pts, wk_mult=1.0):
    """Micros before the learning multiplier and the room cap: the eval size ($800 up to a 25-pt stop, then 800x25/stop)
    times the weekly stop, one rounding, floor 1 (engine/sizing.py lit_qty mode eval)."""
    b = max(1, qty_for(float(risk_pts), EVAL["usd"], EVAL["ref"]))
    return b if wk_mult >= 1 else max(1, int(b * wk_mult + 1e-9))


def _clean(v):
    if isinstance(v, float):
        return None if math.isnan(v) else round(v, 4)
    if hasattr(v, "item"):
        return _clean(v.item())
    return v


def record(t: dict, source: str, f: dict | None = None, post: dict | None = None, qty=None, pnl=None, learn=None,
           logged_at=None) -> dict:
    """One journal record from a finished LIT trade. t: engine/lit_live.py trade shape (entry, stop, target, exit_price,
    exit_reason, pnl, qty, risk_pts, mfe, mae, bars_held, size_mult) or the research unit shape (entry_px, stop_px,
    target_px, exit, legs, risk_pts, ...). qty / pnl: what was traded (routed micros and $); learn: the learning multiplier
    in force at the entry ({"mult", "would", "mode"})."""
    d = int(t["dir"])
    risk = float(t["risk_pts"])
    if "legs" in t:                                     # research unit trade (tools/lit_tightstop.py)
        pts = float(t["legs"][0][1])
        pnl_pm = pts * PV - COMM
        ex = t["exit"]
        entry, stop, tgt = t.get("entry_px"), t.get("stop0_px", t.get("stop_px")), t.get("target_px")
        exit_px = None if entry is None else round(float(entry) + d * pts, 2)
        wk = float(t.get("wk_m", 1.0))
    else:                                               # live trade
        q0 = int(t.get("qty") or 0) or 1
        pnl_pm = float(t["pnl"]) / q0
        ex = t.get("exit_reason") or t.get("exit")
        ex = "EOD" if ex == "TIME" else ex
        entry, stop, tgt, exit_px = t.get("entry"), t.get("stop"), t.get("target"), t.get("exit_price")
        wk = float(t.get("size_mult") or 1.0)
    qp = q_pre_of(risk, wk)
    rec = {"v": VERSION, "key": f"{t['day']}|{int(t['entry_t'])}|{d}", "source": source,
           "logged_at": int(logged_at or time.time()), "day": str(t["day"]), "entry_t": int(t["entry_t"]),
           "exit_t": int(t["exit_t"]) if t.get("exit_t") else None, "dir": d, "side": "LONG" if d == 1 else "SHORT",
           "entry_px": _clean(entry), "stop_px": _clean(stop), "target_px": _clean(tgt), "exit_px": _clean(exit_px),
           "exit": ex, "risk_pts": round(risk, 2), "r": round(pnl_pm / (risk * PV), 3), "pnl_pm": round(pnl_pm, 2),
           "wk_mult": wk, "q_pre": qp, "qty": int(qty) if qty is not None else qp,
           "pnl": round(float(pnl), 2) if pnl is not None else round(pnl_pm * qp, 2),
           "mfe": _clean(t.get("mfe")), "mae": _clean(t.get("mae")), "bars_held": _clean(t.get("bars_held")),
           "swept": list(t.get("swept") or []), "learn": learn or None}
    ff = {k: _clean(v) for k, v in (f or {}).items()}
    rec["f"] = ff
    rec["buckets"] = buckets(ff)
    rec["grade"] = rec["buckets"]["grade"]
    rec["post"] = post or {}
    rec["cause"], rec["tags"] = cause_codes(rec)
    return rec


def load_journal(path: str = JOURNAL_PATH) -> list:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return out


def append_journal(recs: list, path: str = JOURNAL_PATH) -> int:
    """Append-only: a record whose (key, source) is already in the file is never written again (never rewritten)."""
    if not recs:
        return 0
    have = {(r.get("key"), r.get("source")) for r in load_journal(path)}
    new = [r for r in recs if (r["key"], r["source"]) not in have]
    if not new:
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        for r in new:
            fh.write(json.dumps(r, default=str, separators=(",", ":")) + "\n")
    return len(new)


def merged(recs: list) -> list:
    """One record per trade (key): the PC's routed record beats the cloud ledger's, which beats the backtest's."""
    best = {}
    for r in recs:
        k = r.get("key")
        if not k or r.get("exit_t") is None:
            continue
        if k not in best or SOURCE_RANK.get(r.get("source"), 0) > SOURCE_RANK.get(best[k].get("source"), 0):
            best[k] = r
    return sorted(best.values(), key=lambda r: r["entry_t"])


# ------------------------------------------------------------------------------------------------ learning state
def default_learning(mode="observe") -> dict:
    return {"version": VERSION, "mode": mode, "mode_why": "", "updated": None,
            "rules": {"prior_n": PRIOR_N, "bounds": [MULT_LO, MULT_HI], "step_max": STEP_MAX, "skip_min_n": SKIP_MIN_N,
                      "window_days": WINDOW_DAYS, "wf_blocks": WF_BLOCKS, "wf_block_days": WF_BLOCK_DAYS,
                      "wf_min_active": WF_MIN_ACTIVE, "trades_week": list(TPW), "risk_cap_usd": RISK_CAP,
                      "never_changes": "stops, targets, entries, the LIT setup rules, the weekly stop, the Monday rule"},
            "knobs": {}, "decisions": [], "last_review": None, "reviews": []}


_CACHE = {}


def load_learning(path: str | None = None) -> dict | None:
    """The learning file (mtime-cached), or None when absent / unreadable (then every multiplier is 1.0)."""
    p = path or os.environ.get("LE_LIT_LEARNING") or LEARNING_PATH
    try:
        mt = os.stat(p).st_mtime
    except OSError:
        return None
    c = _CACHE.get(p)
    if c and c[0] == mt:
        return c[1]
    try:
        with open(p, encoding="utf-8") as fh:
            L = json.load(fh)
    except Exception:
        return None
    _CACHE[p] = (mt, L)
    return L


def save_learning(L: dict, path: str = LEARNING_PATH):
    L["updated"] = int(time.time())
    tmp = f"{path}.{os.getpid()}.tmp"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(L, fh, indent=1, default=str)
    os.replace(tmp, path)


def _knob(knobs, fam, b):
    return (knobs.get(fam) or {}).get(b) or {}


def mult_of(bk: dict, knobs: dict, override=None):
    """(multiplier clipped to [0.5, 1.25], skip, parts) of one trade's buckets under a knob set. override = (fam, bucket,
    {"mult", "skip"}) replaces one knob (the guardrails' what-if)."""
    m, skip, parts = 1.0, False, []
    for fam, b in (bk or {}).items():
        if b is None:
            continue
        k = _knob(knobs, fam, b)
        if override and override[0] == fam and override[1] == b:
            k = {**k, **override[2]}
        km = float(k.get("mult", 1.0))
        if k.get("skip"):
            skip = True
            parts.append((fam, b, "skip"))
        elif abs(km - 1.0) > 1e-9:
            m *= km
            parts.append((fam, b, km))
    return min(MULT_HI, max(MULT_LO, m)), skip, parts


def learn_mult(trade: dict | None, learning: dict | None) -> dict:
    """The learning layer for one entry: {"mult" (applied: 1.0 unless mode apply), "skip" (applied), "would", "would_skip",
    "mode", "buckets", "reasons"}. No learning file / no features: 1.0, nothing logged."""
    out = {"mult": 1.0, "skip": False, "would": 1.0, "would_skip": False, "mode": None, "buckets": None, "reasons": []}
    if not learning:
        return out
    bk = None
    if trade:
        lr = trade.get("learn") or {}
        bk = lr.get("buckets") or (buckets(lr["f"]) if lr.get("f") else None)
    out["mode"] = learning.get("mode") or "observe"
    if not bk:
        return out
    out["buckets"] = bk
    m, skip, parts = mult_of(bk, learning.get("knobs") or {})
    out["would"], out["would_skip"] = round(m, 4), skip
    if out["mode"] == "apply":
        out["mult"], out["skip"] = m, skip
        if skip:
            out["reasons"].append("learned skip: " + ", ".join(bucket_label(f, b) for f, b, v in parts if v == "skip"))
        elif abs(m - 1.0) > 1e-9:
            out["reasons"].append(f"learned x{m:.2f} (" + ", ".join(f"{FAMILIES[f][1].get(b, b)} x{v:g}" for f, b, v in parts
                                                                   if v != "skip") + ")")
    return out


# ------------------------------------------------------------------------------------------------ evaluation on journal records
def qty_learn(q_pre: int, m: float, risk_pts: float) -> int:
    """engine/sizing.py lit_qty's learning step: one rounding with the weekly stop, floor 1, max 40, a size-up never risks
    more than RISK_CAP (= tools/lit_select.py qty_sel)."""
    if abs(m - 1.0) < 1e-9:
        return int(q_pre)
    q = max(1, min(40, int(q_pre * m + 1e-9)))
    if m > 1.0:
        q = max(1, min(q, int(RISK_CAP / (float(risk_pts) * PV + COMM))))
    return q


def _weekdays(a: str, z: str) -> list:
    d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(z)
    out = []
    while d0 <= d1:
        if d0.weekday() < 5:
            out.append(d0.isoformat())
        d0 += dt.timedelta(days=1)
    return out


def _sized(recs, knobs, override=None):
    out = []
    for r in recs:
        m, skip, _ = mult_of(r.get("buckets") or {}, knobs, override)
        q = 0 if skip else qty_learn(int(r["q_pre"]), m, float(r["risk_pts"]))
        out.append((r, q, float(r["pnl_pm"]) * q))
    return out


def simulate(recs: list, knobs: dict, a: str | None = None, z: str | None = None, override=None, sessions=None,
             evals: bool = True) -> dict:
    """The journal's trades in [a, z] re-sized under a knob set (exact: P&L is linear in micros). Money at the eval size
    without the room cap; eval odds from a fresh MFFU 50K eval on every session (weekdays, or `sessions`) with the 60% room
    cap: p10/f10 = passed/failed within 10 sessions, p20/f20 within 20."""
    R = [r for r in recs if (a is None or r["day"] >= a) and (z is None or r["day"] <= z)]
    if not R:
        return {"n": 0, "taken": 0, "net": 0.0, "pf": None, "dd": 0.0, "tpw": 0.0, "p10": None, "f10": None, "p20": None, "f20": None}
    a = a or R[0]["day"]
    z = z or R[-1]["day"]
    S = _sized(R, knobs, override)
    P = [p for r, q, p in S if q > 0]
    gl = -sum(p for p in P if p < 0)
    eq, peak, dd = 0.0, 0.0, 0.0
    for p in P:
        eq += p
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    ss = sessions or _weekdays(a, z)
    ss = [s for s in ss if a <= s <= z]
    weeks = max(1e-9, len(ss) / 5.0)
    out = {"n": len(R), "taken": len(P), "net": round(sum(P), 2), "pf": round(sum(p for p in P if p > 0) / gl, 2) if gl else None,
           "dd": round(dd, 2), "tpw": round(len(P) / weeks, 2), "r_sum": round(sum(float(r["r"]) for r, q, p in S if q > 0), 2)}
    if evals:
        by = collections.defaultdict(list)
        for r, q, p in S:
            if q > 0:
                by[r["day"]].append((r, q))
        res = [_play(ss, by, i) for i in range(len(ss))]
        N = len(res) or 1
        for H in (10, 20):
            out[f"p{H}"] = round(100 * sum(1 for x, n in res if x == "PASS" and n <= H) / N, 1)
            out[f"f{H}"] = round(100 * sum(1 for x, n in res if x == "FAIL" and n <= H) / N, 1)
    return out


def _play(ss, by, i0, H=20):
    E = EVAL
    bal = peak = E["start"]
    mll = bal - E["mll"]
    for k in range(i0, min(len(ss), i0 + H)):
        cum = low = 0.0
        for r, q in by.get(ss[k], []):
            room = bal + cum - mll
            q = min(q, max(1, int(E["room_k"] * max(0.0, room) / (float(r["risk_pts"]) * PV))))
            mae = _num(r.get("mae"))
            worst = -(mae if mae is not None else 1.0) * float(r["risk_pts"]) * PV * q - COMM * q
            pnl = float(r["pnl_pm"]) * q
            low = min(low, cum + min(0.0, worst, pnl))
            cum += pnl
            low = min(low, cum)
        if bal + low <= mll or bal + cum <= mll:
            return "FAIL", k - i0 + 1
        bal += cum
        peak = max(peak, bal)
        mll = min(max(mll, peak - E["mll"]), E["lock"])
        if bal - E["start"] >= E["target"]:
            return "PASS", k - i0 + 1
    return "OPEN", H


# ------------------------------------------------------------------------------------------------ estimation
def estimate(recs: list, prior_n: float | None = None) -> dict:
    """Per bucket: n, mean R, $ at the eval base size, the shrunk mean R (prior worth prior_n trades at the overall mean)
    and the target multiplier = shrunk mean / overall mean, clipped to [0.5, 1.25] (1.0 when the overall mean R is not
    positive: no edge to allocate). skip_ok: >= 15 trades that lost money at the base size."""
    prior_n = PRIOR_N if prior_n is None else prior_n
    if not recs:
        return {"n": 0, "rbar": None, "fam": {}}
    rbar = sum(float(r["r"]) for r in recs) / len(recs)
    acc = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0.0, 0.0]))
    for r in recs:
        for fam, b in (r.get("buckets") or {}).items():
            if b is None or fam not in FAMILIES:
                continue
            x = acc[fam][b]
            x[0] += 1
            x[1] += float(r["r"])
            x[2] += float(r["pnl_pm"]) * int(r["q_pre"])
    out = {}
    for fam in acc:
        if ACTIVE is not None and fam not in ACTIVE:
            continue
        out[fam] = {}
        for b, (n, sr, usd) in acc[fam].items():
            post = (sr + prior_n * rbar) / (n + prior_n)
            tg = min(MULT_HI, max(MULT_LO, post / rbar)) if rbar > 0.05 else 1.0
            out[fam][b] = {"n": n, "mean_r": round(sr / n, 3), "usd": round(usd, 2), "post_r": round(post, 3),
                           "target": round(tg, 3), "skip_ok": bool(n >= SKIP_MIN_N and usd < 0)}
    return {"n": len(recs), "rbar": round(rbar, 3), "fam": out}


def _grid(x):
    return round(round(x / STEP) * STEP, 2)


def proposal_value(cur: float, target: float) -> float:
    """Move from the current knob toward the target by at most STEP_MAX, on the 0.05 grid, inside [0.5, 1.25]."""
    v = cur + max(-STEP_MAX, min(STEP_MAX, target - cur))
    return min(MULT_HI, max(MULT_LO, _grid(v)))


def _asof_ts(asof: str) -> int:
    return int(dt.datetime.combine(dt.date.fromisoformat(asof), dt.time(0, 0), ET).timestamp())


def _visible(recs, asof):
    ts = _asof_ts(asof)
    return [r for r in merged(recs) if r.get("exit_t") is not None and int(r["exit_t"]) <= ts and r["day"] < asof]


def _shift(day: str, days: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=days)).isoformat()


# ------------------------------------------------------------------------------------------------ guardrails
def _halves(V, asof):
    """The 2026 H1/H2 split of the visible history (H2 from Jul 1 once both halves have 20+ trades), else the visible data
    cut in two at its middle trade. Returns ((a1, z1), (a2, z2), how)."""
    if not V:
        return None
    first = V[0]["day"]
    yr = asof[:4]
    cut = f"{yr}-07-01"
    h1 = [r for r in V if r["day"] < cut and r["day"] >= f"{yr}-01-01"]
    h2 = [r for r in V if r["day"] >= cut]
    if len(h1) >= MIN_TRADES and len(h2) >= MIN_TRADES and first >= f"{yr}-01-01":
        return (first, _shift(cut, -1)), (cut, V[-1]["day"]), f"{yr} H1 / H2 (Jul 1)"
    mid = V[len(V) // 2]["day"]
    return (first, _shift(mid, -1)), (mid, V[-1]["day"]), f"visible history cut at {mid}"


def guardrails(V: list, knobs: dict, cand: dict, asof: str, wf: dict, sessions=None) -> dict:
    """Every check of one proposal. V = visible merged journal records (exit before asof), cand = {"fam", "b", "kind",
    "value"}; wf = the walk-forward block estimates (_wf_blocks)."""
    fam, b = cand["fam"], cand["b"]
    cur = _knob(knobs, fam, b)
    ov = (fam, b, {"skip": True} if cand["kind"] == "skip" else {"skip": False, "mult": cand["value"]} if cand["kind"] == "unskip"
          else {"mult": cand["value"]})
    w0 = _shift(asof, -WINDOW_DAYS)
    win_first = max(w0, V[0]["day"]) if V else w0
    last = _shift(asof, -1)
    checks = {}
    # a. walk-forward: the learning rule for this bucket, re-estimated before each block
    delta, active, rows = 0.0, 0, []
    for blk in wf["blocks"]:
        est = blk["est"]["fam"].get(fam, {}).get(b)
        if est is None or blk["est"]["n"] < MIN_TRADES:
            rows.append({"block": blk["a"], "active": False, "why": "too little data before it"})
            continue
        cm = float(cur.get("mult", 1.0))
        if cand["kind"] == "skip":
            ovb = (fam, b, {"skip": True}) if est["skip_ok"] else None
        elif cand["kind"] == "unskip":
            ovb = (fam, b, {"skip": False, "mult": cm}) if not est["skip_ok"] else None
        else:
            v = proposal_value(cm, est["target"])
            ovb = (fam, b, {"mult": v}) if abs(v - cm) >= STEP - 1e-9 and (v - cm) * (cand["value"] - cm) > 0 else None
        T = [r for r in V if blk["a"] <= r["day"] < blk["z"] and (r.get("buckets") or {}).get(fam) == b]
        if ovb is None or not T:
            rows.append({"block": blk["a"], "active": False, "n": len(T)})
            continue
        d_ = sum(p for _, _, p in _sized(T, knobs, ovb)) - sum(p for _, _, p in _sized(T, knobs))
        delta += d_
        active += 1
        rows.append({"block": blk["a"], "active": True, "n": len(T), "delta": round(d_, 2), "value": ovb[2]})
    checks["walk_forward"] = {"pass": active >= WF_MIN_ACTIVE and delta > 0, "delta_usd": round(delta, 2), "active_blocks": active,
                              "need_blocks": WF_MIN_ACTIVE, "blocks": rows}
    # a. both halves of the visible history
    hv = _halves(V, asof)
    hres = []
    ok = True
    for (ha, hz) in hv[:2]:
        s0 = simulate(V, knobs, ha, hz, evals=False)
        s1 = simulate(V, knobs, ha, hz, override=ov, evals=False)
        d_ = s1["net"] - s0["net"]
        hres.append({"from": ha, "to": hz, "before": s0["net"], "after": s1["net"], "delta": round(d_, 2)})
        ok = ok and d_ > 0
    checks["halves"] = {"pass": ok, "split": hv[2], "halves": hres}
    # b. trades a week (trailing 6 months)
    s0 = simulate(V, knobs, win_first, last, sessions=sessions)
    s1 = simulate(V, knobs, win_first, last, override=ov, sessions=sessions)
    checks["trades_week"] = {"pass": s1["tpw"] >= TPW[0] - 1e-9 or s1["tpw"] >= s0["tpw"] - 1e-9, "before": s0["tpw"],
                             "after": s1["tpw"], "band": list(TPW)}
    # c. MFFU 2-week fail rate: trailing 6 months and the whole visible history
    a0 = simulate(V, knobs, sessions=sessions)
    a1 = simulate(V, knobs, override=ov, sessions=sessions)
    checks["eval_fail_2wk"] = {"pass": s1["f10"] <= s0["f10"] + 1e-9 and a1["f10"] <= a0["f10"] + 1e-9,
                               "recent_before": s0["f10"], "recent_after": s1["f10"], "all_before": a0["f10"], "all_after": a1["f10"]}
    # e. signal: is the bucket really different from the rest (not chance)? Only for a move away from 1.0x or a skip
    W = [r for r in V if r["day"] >= w0]
    zz = welch_z(W, fam, b)
    away = cand["kind"] == "skip" or (cand["kind"] == "mult" and abs(cand["value"] - 1.0) > abs(float(cur.get("mult", 1.0)) - 1.0) + 1e-9)
    if not away:
        sig_ok = True
    elif cand["kind"] == "skip":
        sig_ok = zz is not None and zz <= -Z_MIN
    else:
        sig_ok = zz is not None and abs(zz) >= Z_MIN and (zz > 0) == (cand["value"] > float(cur.get("mult", 1.0)))
    checks["signal"] = {"pass": bool(sig_ok), "z": None if zz is None else round(zz, 2), "need": Z_MIN, "away_from_1": away}
    # d. size of the step (one bucket a week is enforced by review())
    cm = float(cur.get("mult", 1.0))
    checks["max_step"] = {"pass": cand["kind"] != "mult" or abs(cand["value"] - cm) <= STEP_MAX + 1e-9, "from": cm,
                          "to": cand.get("value")}
    return {"pass": all(c["pass"] for c in checks.values()), "checks": checks,
            "numbers": {"recent": {"before": s0, "after": s1, "from": win_first, "to": last},
                        "all": {"before": a0, "after": a1}}}


def welch_z(W, fam, b):
    """z of the bucket's mean R vs the rest of W, with the pooled spread of all of W (a small bucket of all losers has no
    spread of its own and would look certain); R winsorized at +/-WINSOR. None with fewer than SIG_MIN_N trades on a side."""
    a = [max(-WINSOR, min(WINSOR, float(r["r"]))) for r in W if (r.get("buckets") or {}).get(fam) == b]
    c = [max(-WINSOR, min(WINSOR, float(r["r"]))) for r in W if (r.get("buckets") or {}).get(fam) != b]
    if len(a) < SIG_MIN_N or len(c) < SIG_MIN_N:
        return None
    allr = a + c
    m = sum(allr) / len(allr)
    sd = math.sqrt(sum((x - m) ** 2 for x in allr) / (len(allr) - 1))
    se = sd * math.sqrt(1.0 / len(a) + 1.0 / len(c))
    return (sum(a) / len(a) - sum(c) / len(c)) / se if se > 0 else None


def _wf_blocks(V, asof):
    out = []
    for j in range(WF_BLOCKS, 0, -1):
        a = _shift(asof, -j * WF_BLOCK_DAYS)
        z = _shift(asof, -(j - 1) * WF_BLOCK_DAYS)
        ts = _asof_ts(a)
        train = [r for r in V if int(r["exit_t"]) <= ts and r["day"] < a and r["day"] >= _shift(a, -WINDOW_DAYS)]
        out.append({"a": a, "z": z, "est": estimate(train)})
    return {"blocks": out}


# ------------------------------------------------------------------------------------------------ the weekly review
def _next_id(L):
    return f"d{len(L.get('decisions') or []) + 1:04d}"


def candidates(est: dict, knobs: dict) -> list:
    out = []
    for fam, bs in est["fam"].items():
        for b, x in bs.items():
            k = _knob(knobs, fam, b)
            cm = float(k.get("mult", 1.0))
            if k.get("skip"):
                if not x["skip_ok"]:
                    out.append({"fam": fam, "b": b, "kind": "unskip", "value": cm, "est": x})
                continue
            v = proposal_value(cm, x["target"])
            if abs(v - cm) >= STEP - 1e-9:
                out.append({"fam": fam, "b": b, "kind": "mult", "value": v, "est": x})
            if x["skip_ok"]:
                out.append({"fam": fam, "b": b, "kind": "skip", "value": None, "est": x})
    return out


def review(recs: list, L: dict | None, asof: str, sessions=None, source: str = "weekly") -> tuple:
    """The Sunday review as of `asof` (YYYY-MM-DD, a Sunday; only trades that finished before it). Returns (new learning
    state, decision). At most one knob changes, and only after every guardrail passes; the decision is logged either way."""
    L = copy.deepcopy(L) if L else default_learning()
    knobs = L.setdefault("knobs", {})
    V = [r for r in _visible(recs, asof) if r["day"] >= _shift(asof, -HISTORY_DAYS)]
    w0 = _shift(asof, -WINDOW_DAYS)
    W = [r for r in V if r["day"] >= w0]
    dec = {"id": _next_id(L), "asof": asof, "at": int(time.time()), "source": source, "mode": L.get("mode"),
           "action": "none", "fam": None, "bucket": None, "before": None, "after": None, "reason": "", "evidence": {},
           "numbers": {}, "applied": False}
    if len(W) < MIN_TRADES:
        dec["reason"] = f"not enough trades to learn from: {len(W)} in the last 6 months (needs {MIN_TRADES})"
        return _finish(L, dec, [], {"n": len(W)}, asof)
    est = estimate(W)
    wf = _wf_blocks(V, asof)
    C = candidates(est, knobs)
    tested = []
    for c in C:
        g = guardrails(V, knobs, c, asof, wf, sessions=sessions)
        tested.append({**c, "pass": g["pass"], "checks": g["checks"], "numbers": g["numbers"]})
    ok = [t for t in tested if t["pass"]]
    if not C:
        dec["reason"] = "every knob is where the evidence says (no bucket would move by 0.05x or more)"
    elif not ok:
        fails = collections.Counter(k for t in tested for k, v in t["checks"].items() if not v["pass"])
        dec["reason"] = (f"{len(C)} proposal(s), none passed the guardrails (failed: "
                         + ", ".join(f"{k} {n}" for k, n in fails.most_common()) + "): every knob stays")
    else:
        best = max(ok, key=lambda t: t["checks"]["walk_forward"]["delta_usd"])
        fam, b = best["fam"], best["b"]
        before = dict(_knob(knobs, fam, b)) or {"mult": 1.0, "skip": False}
        after = dict(before)
        if best["kind"] == "skip":
            after["skip"] = True
        elif best["kind"] == "unskip":
            after["skip"] = False
        else:
            after["mult"] = best["value"]
        after.update(since=asof, decision=dec["id"])
        knobs.setdefault(fam, {})[b] = after
        x = best["est"]
        dec.update(action=best["kind"], fam=fam, bucket=b, before={k: before.get(k) for k in ("mult", "skip")},
                   after={k: after.get(k) for k in ("mult", "skip")}, applied=L.get("mode") == "apply",
                   reason=(f"{bucket_label(fam, b)}: {x['n']} trades, mean {x['mean_r']:+.2f}R vs {est['rbar']:+.2f}R overall "
                           f"(shrunk {x['post_r']:+.2f}R, prior {PRIOR_N:g} trades) -> "
                           + ("skip (lost money with 15+ trades)" if best["kind"] == "skip" else
                              "skip lifted" if best["kind"] == "unskip" else
                              f"x{before.get('mult', 1.0):g} -> x{best['value']:g} (target x{x['target']:g})")
                           + f"; walk-forward {best['checks']['walk_forward']['delta_usd']:+,.0f} $ on "
                             f"{best['checks']['walk_forward']['active_blocks']} blocks, both halves better, eval 2-wk fails not up"
                           + ("" if L.get("mode") == "apply" else " (observe mode: logged, not applied to the size)")),
                   evidence={"estimate": x, "rbar": est["rbar"], "checks": best["checks"]}, numbers=best["numbers"])
    return _finish(L, dec, tested, est, asof)


def _finish(L, dec, tested, est, asof):
    L.setdefault("decisions", []).append(dec)
    short = [{"fam": t["fam"], "b": t["b"], "kind": t["kind"], "value": t["value"], "pass": t["pass"],
              "n": t["est"]["n"], "mean_r": t["est"]["mean_r"], "target": t["est"]["target"],
              "failed": [k for k, v in t["checks"].items() if not v["pass"]],
              "wf_delta": t["checks"]["walk_forward"]["delta_usd"], "halves": [h["delta"] for h in t["checks"]["halves"]["halves"]],
              "f10": [t["checks"]["eval_fail_2wk"]["recent_before"], t["checks"]["eval_fail_2wk"]["recent_after"]]}
             for t in tested]
    L["last_review"] = {"asof": asof, "decision": dec["id"], "action": dec["action"], "reason": dec["reason"],
                        "trades": est.get("n"), "rbar": est.get("rbar"), "proposals": short,
                        "buckets": {fam: {b: {k: x[k] for k in ("n", "mean_r", "usd", "post_r", "target", "skip_ok")}
                                          for b, x in bs.items()} for fam, bs in (est.get("fam") or {}).items()}}
    L.setdefault("reviews", []).append({"asof": asof, "decision": dec["id"], "action": dec["action"], "fam": dec["fam"],
                                        "bucket": dec["bucket"], "after": dec["after"], "proposals": len(short),
                                        "passed": sum(1 for s in short if s["pass"])})
    L["reviews"] = L["reviews"][-200:]
    return L, dec


def revert(L: dict, decision_id: str, reason: str = "reverted by hand") -> tuple:
    """Undo one decision: the knob goes back to the value before it; the revert is logged as its own decision."""
    L = copy.deepcopy(L)
    d = next((x for x in L.get("decisions") or [] if x["id"] == decision_id), None)
    if d is None or not d.get("fam"):
        raise ValueError(f"no knob change with id {decision_id}")
    fam, b = d["fam"], d["bucket"]
    cur = _knob(L["knobs"], fam, b)
    back = {**(d.get("before") or {"mult": 1.0, "skip": False})}
    rid = _next_id(L)
    if abs(float(back.get("mult", 1.0)) - 1.0) < 1e-9 and not back.get("skip"):
        L["knobs"].get(fam, {}).pop(b, None)
    else:
        L["knobs"].setdefault(fam, {})[b] = {**back, "since": dt.date.today().isoformat(), "decision": rid}
    L["decisions"].append({"id": rid, "asof": dt.date.today().isoformat(), "at": int(time.time()), "source": "manual",
                           "mode": L.get("mode"), "action": "revert", "of": decision_id, "fam": fam, "bucket": b,
                           "before": {k: cur.get(k) for k in ("mult", "skip")}, "after": back, "reason": reason,
                           "evidence": {}, "numbers": {}, "applied": L.get("mode") == "apply"})
    return L, L["decisions"][-1]


def set_mode(L: dict, mode: str, why: str = "") -> dict:
    if mode not in ("observe", "apply"):
        raise ValueError(mode)
    L = copy.deepcopy(L)
    L["mode"], L["mode_why"] = mode, why
    return L


def last_sunday(day: dt.date) -> str:
    """The most recent Sunday on or before `day` (the review date of its week)."""
    return (day - dt.timedelta(days=(day.weekday() + 1) % 7)).isoformat()


def review_due(L: dict | None, today: dt.date) -> str | None:
    """The Sunday whose review has not run yet (the weekly review runs on Sunday, or on the first run after it)."""
    s = last_sunday(today)
    last = ((L or {}).get("last_review") or {}).get("asof")
    return s if (last is None or last < s) else None


# ------------------------------------------------------------------------------------------------ dashboard block
def summary(L: dict | None, recs: list, today: str | None = None) -> dict:
    """state.json / data.json "learning": the mode, the knobs in force (applied or shadow), the last review, the decisions
    log and this month's loss causes."""
    today = today or dt.date.today().isoformat()
    L = L or default_learning()
    J = merged(recs)
    month = today[:7]
    lm = [r for r in J if r["day"][:7] == month and r.get("cause")]
    by = collections.defaultdict(lambda: [0, 0.0, 0.0])
    for r in lm:
        x = by[r["cause"]]
        x[0] += 1; x[1] += float(r.get("pnl") or 0); x[2] += float(r.get("r") or 0)
    tags = collections.Counter(t for r in lm for t in r.get("tags") or [])
    knobs = [{"family": fam, "bucket": b, "label": bucket_label(fam, b), "mult": k.get("mult", 1.0), "skip": bool(k.get("skip")),
              "since": k.get("since"), "decision": k.get("decision")}
             for fam, bs in (L.get("knobs") or {}).items() for b, k in bs.items()]
    src = collections.Counter(r.get("source") for r in J)
    return {"mode": L.get("mode") or "observe", "mode_why": L.get("mode_why") or "",
            "applied": (L.get("mode") == "apply"),
            "text": ("The bot sizes trades with what it learned (bounded 0.5x-1.25x)." if L.get("mode") == "apply" else
                     "Observe mode: the bot logs what it would change; the size is not touched."),
            "knobs": knobs, "rules": L.get("rules") or default_learning()["rules"],
            "last_review": {k: v for k, v in (L.get("last_review") or {}).items() if k != "buckets"} or None,
            "buckets": (L.get("last_review") or {}).get("buckets"),
            "decisions": [{k: d.get(k) for k in ("id", "asof", "action", "fam", "bucket", "before", "after", "reason", "applied", "of")}
                          for d in (L.get("decisions") or [])][-20:],
            "changes": [d["id"] for d in L.get("decisions") or [] if d.get("action") not in ("none",)],
            "causes_month": {"month": month, "losses": len(lm), "usd": round(sum(float(r.get("pnl") or 0) for r in lm), 2),
                             "by_cause": [{"cause": c, "label": CAUSES.get(c, c), "n": v[0], "usd": round(v[1], 2), "r": round(v[2], 2)}
                                          for c, v in sorted(by.items(), key=lambda kv: kv[1][1])],
                             "tags": [{"tag": t, "label": CAUSES.get(t, t), "n": n} for t, n in tags.most_common()]},
            "journal": {"n": len(J), "by_source": dict(src), "first_day": J[0]["day"] if J else None,
                        "last_day": J[-1]["day"] if J else None},
            "history_replay": L.get("history_replay")}


# ------------------------------------------------------------------------------------------------ live features
def live_features(M, C, trades, P, es_df=None, only_after: int | None = None) -> dict:
    """{(day, i, dir): {"f": features, "buckets", "grade", "post"}} for the live loop's trades (engine/lit_live.py), the
    same 50 features as the research (tools/lit_select.py feats on the live market window) + the 4H draw. trades: the
    executor's trades (with "i", "dir", "day"); only_after: skip trades that finished before this unix time (their
    journal record is written already). Never raises: a failure returns {} (sizing then stays at 1.0)."""
    out = {}
    try:
        import numpy as np
        from tools import lit_select as S
        want = [t for t in trades if t.get("i") is not None and (only_after is None or t.get("exit_t") is None
                                                                  or int(t.get("exit_t") or 0) >= only_after or t.get("exit") == "OPEN")]
        if not want:
            return out
        if es_df is not None and len(es_df):
            es = es_df.drop_duplicates("time").set_index("time").reindex(M.t)
            ES = {"h": es["high"].values.astype(float), "l": es["low"].values.astype(float), "c": es["close"].values.astype(float)}
        else:
            nan = np.full(M.n, np.nan)
            ES = {"h": nan, "l": nan, "c": nan}
        NEWS = S.news_cal()
        WK = S.week_open_close(M)
        PU = {**P}
        days = {t["day"] for t in want}
        acc = collections.defaultdict(list)
        zmap = {}
        for z in C:
            if z["day"] not in days:
                continue
            pl = S.plan_of(M, z, PU)
            if pl is None:
                continue
            zmap[(z["day"], z["i"], z["dir"])] = (z, pl, list(acc[z["day"]]))
            acc[z["day"]].append(z)
        hist_all = sorted([{"r1": (float(t["exit_px"]) - float(t["entry_px"])) * t["dir"] / float(t["risk_pts"]),
                            "exit": t["exit"], "day": t["day"], "exit_t": t["exit_t"]}
                           for t in trades if t.get("exit") not in (None, "OPEN") and t.get("exit_px") is not None],
                          key=lambda h: h["exit_t"])
        for t in want:
            key = (t["day"], int(t["i"]), int(t["dir"]))
            if key not in zmap:
                continue
            z, pl, same = zmap[key]
            t_sig = int(M.t[z["i"]]) + 300
            hist = [h for h in hist_all if int(h["exit_t"]) <= t_sig]
            f = S.feats(M, z, pl, ES, NEWS, WK, same, hist)
            f.update(h4_feats(M, z["i"], z["dir"]))
            f = {k: _clean(v) for k, v in f.items()}
            out[key] = {"f": f, "buckets": buckets(f), "grade": trader_grade(f)}
    except Exception as e:                       # the learning layer must never stop the live loop
        out["_error"] = f"{e.__class__.__name__}: {e}"
    return out


# ------------------------------------------------------------------------------------------------ CLI
def _cli(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.lit_learn")
    ap.add_argument("cmd", choices=["status", "review", "revert", "mode", "pull", "selftest"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--asof")
    ap.add_argument("--journal", default=JOURNAL_PATH)
    ap.add_argument("--learning", default=LEARNING_PATH)
    ap.add_argument("--why", default="")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return 0 if selftest() else 1
    L = load_learning(a.learning) or default_learning()
    if a.cmd == "status":
        print(json.dumps(summary(L, load_journal(a.journal)), indent=1, default=str))
    elif a.cmd == "review":
        asof = a.asof or last_sunday(dt.date.today())
        L2, d = review(load_journal(a.journal), L, asof, source="manual")
        save_learning(L2, a.learning)
        print(d["id"], d["action"], d["reason"])
    elif a.cmd == "revert":
        L2, d = revert(L, a.arg, a.why or "reverted by hand")
        save_learning(L2, a.learning)
        print(d["id"], "reverted", a.arg)
    elif a.cmd == "mode":
        save_learning(set_mode(L, a.arg, a.why), a.learning)
        print("mode", a.arg)
    elif a.cmd == "pull":
        import subprocess
        subprocess.run(["git", "fetch", "-q", "--depth", "1", "origin", "dashboard"], cwd=ROOT, check=True)
        for name, dst in (("lit_learning.json", a.learning), ("lit_journal.jsonl", None)):
            r = subprocess.run(["git", "show", f"FETCH_HEAD:{name}"], cwd=ROOT, capture_output=True)
            if r.returncode == 0 and dst:
                with open(dst, "wb") as fh:
                    fh.write(r.stdout)
                print("pulled", name, "->", dst)
            elif r.returncode == 0:
                recs = [json.loads(x) for x in r.stdout.decode().splitlines() if x.strip()]
                print("pulled", name, ":", append_journal(recs, a.journal), "new records ->", a.journal)
    return 0


def selftest() -> bool:
    from tests.test_lit_learn import run_all
    return run_all()


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
