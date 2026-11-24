"""BLITZ learns from its mistakes, HONESTLY (owner 2026-11-24: BLITZ "shouldn't be set and tuned, it should learn from mistakes").
RESEARCH AND REPORTING ONLY: nothing here sizes, pauses, arms or edits a live setting. A live rule changes only after a fix passes
the strategy-test protocol below AND the owner says yes on the Decide card (then Claude builds it as a normal change, with proof).

    python -X utf8 research/blitz/learn.py night            # tag new BLITZ trades; on Sunday (ET) also the weekly re-test
    python -X utf8 research/blitz/learn.py tag              # only tag the new trades -> research/blitz/lessons.jsonl
    python -X utf8 research/blitz/learn.py weekly --force   # the weekly re-test now (any day) [--ne 2000 --ns 1000] [--no-push]
    python -X utf8 research/blitz/learn.py status           # lessons by tag, candidates, the multiple-test count
Runs in the cloud as tools/learn_night.py step "blitz" (after the PC's day folders are pulled). Tests: tests/test_blitz_learn.py.

1. LESSONS (every night). Every closed BLITZ trade (paper on account C, sim / live on the Rapid's lane) in the pulled day folders
   (engine/zeus_learn.signals) gets one row in research/blitz/lessons.jsonl, once (key mode|entry_t|dir). A loser's tags say why
   it may have lost; winners get the same tags so a tag's NET R is honest (a tag that loses on its losers but wins more on its
   winners is not a mistake):
     stopped_at_sweep  full stop-out (the stop sits 1 tick beyond the sweep extreme, so price took the sweep out again)
     wide_stop         the stop was > 1.5x the median of BLITZ's last 20 stops
     chased            filled >= 2 ticks worse than the planned entry (live / sim fills only)
     news              a high-impact release from 15 min before the entry to the exit (data/news, engine.news.historical_events)
     overlap_lit       Zlarior (LIT) was in a trade, or had exited < 30 min before (the one-position / no-hedge rules bite here)
     after_loss        an earlier BLITZ loser the same day
     late_day          entered at or after 15:00 ET
     best_day_cap      BLITZ had already closed >= 50% of the Rapid's 30% best-day guide ($427.50) that day ($ known paper / live)
     other             a loser with none of the above
2. WEEKLY (Sunday ET, once an ISO week). The tags are ranked by NET R over the last 8 weeks of lessons (fewer than 20 lessons:
   the newest 120 backtest sessions, said so). The top 1-2 tags that have a testable fix (CANDIDATES; chased / best_day_cap /
   other / stopped_at_sweep have none (UNTESTABLE: reported only) are re-tested:
     a. the 3 spans (strategy-test protocol: Jan-Jun 2026, Jul-Oct 2026, 2021-25) on the Rapid EOD 25K eval book of
        research/pillars/blitz_rapid.py, the CURRENT live lane (BLITZ $engine.rapid_blitz.BLITZ_USD, one position) vs the same with
        the fix, costs in, 2,000 eval / 1,000 six-month paths. PASS = both 2026 halves +$25 a month or more with eval fail% at most
        +0.5 pt, and 2021-25 not worse than -$25 a month / +1.0 pt fail;
     b. FRESH, UNTOUCHED data: only paper / live BLITZ trades closed AFTER the fix was first picked (its "fresh_from" day; the
        data that picked it never counts). PASS = at least 30 fresh trades, the trades the fix would have removed lost R in
        total, and a bootstrap p (removed trades' mean R >= 0) <= 0.05 / k, where k = every BLITZ fix test ever run
        (research/blitz/tests.jsonl, this one included): the multiple tests are counted, so more tries need stronger proof.
   Fewer than 30 fresh trades = "waiting for fresh data", never a pass. Every test is logged (tests.jsonl), passed or not.
3. When a fix passes both: ONE Decide card ("BLITZ learned X: +$Y/mo, fails Z%", status open, yes / no / later) on
   tools/web_public/business/decisions.json and ONE phone line (the private ntfy topic of tools/pc_report.py), once per fix.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import statistics
import sys
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
LESSONS = os.path.join(HERE, "lessons.jsonl")
TESTS = os.path.join(HERE, "tests.jsonl")
STATE = os.path.join(HERE, "state.json")
WEEKLY = os.path.join(HERE, "weekly.json")
DECISIONS = os.path.join(ROOT, "tools", "web_public", "business", "decisions.json")
PC_DAYS = os.path.join(ROOT, "data", "pc_days")
PROTECTED = ("live_model.json", "live_model_lit.json", "live_model_engine.json", "second_model.json", "data/rapid.json",
             "data/account_b.json")

TAGS = ("stopped_at_sweep", "wide_stop", "chased", "news", "overlap_lit", "after_loss", "late_day", "best_day_cap", "other")
NEWS_BEFORE, LIT_GAP = 15 * 60, 30 * 60
WIDE_X, WIDE_N = 1.5, 20
CHASE_TICKS = 2.0
LATE_H = 15
BEST_DAY_GUIDE = 0.3 * 1500 * 0.95            # engine/rapid.best_day_cap on the Rapid EOD 25K
WINDOW_DAYS, MIN_LESSONS, MIN_TAG_N, TOP = 56, 20, 8, 2
FRESH_MIN, ALPHA, BOOT = 30, 0.05, 4000
GAIN_MO, FAIL_PT, REF_MO, REF_FAIL = 25.0, 0.5, 25.0, 1.0
RETRY_DAYS = 28                                # a rejected fix waits 4 weeks before it is picked again (it still counts in k)


# ================================================================================================ small helpers
def _f(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def read_jsonl(p):
    out = []
    try:
        with open(p, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def append_jsonl(p, rows):
    if not rows:
        return
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")


def read_json(p, d=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return d


def write_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, p)


def news_times(impacts=("high",)) -> list:
    try:
        from engine import news
        return sorted(int(e["t"]) for e in news.historical_events(impacts))
    except Exception:
        return []


# ================================================================================================ 1. tags
def tags_of(t: dict, ctx: dict) -> list:
    """The reasons on one BLITZ trade t (research shape: entry_t, exit_t, risk (pts), pts, day; live adds slip_ticks / usd).
    ctx: lit = [(entry_t, exit_t)] of Zlarior that day, news = sorted event epochs, prev = earlier BLITZ trades that day
    (pts, usd), risk_med = the median of BLITZ's last 20 stops (pts) or None, day_usd = that day's closed $ before the entry."""
    et_, xt = int(t["entry_t"]), int(t.get("exit_t") or t["entry_t"])
    risk, pts = _f(t.get("risk")), _f(t.get("pts"), 0.0)
    out = []
    if risk and pts <= -0.95 * risk:
        out.append("stopped_at_sweep")
    if risk and ctx.get("risk_med") and risk > WIDE_X * float(ctx["risk_med"]):
        out.append("wide_stop")
    if _f(t.get("slip_ticks")) is not None and float(t["slip_ticks"]) >= CHASE_TICKS:
        out.append("chased")
    if any(et_ - NEWS_BEFORE <= n <= xt for n in ctx.get("news") or ()):
        out.append("news")
    if any(le <= et_ <= lx + LIT_GAP for le, lx in ctx.get("lit") or ()):
        out.append("overlap_lit")
    if any(_f(p.get("pts"), 0.0) < 0 for p in ctx.get("prev") or ()):
        out.append("after_loss")
    if _et(et_).hour >= LATE_H:
        out.append("late_day")
    if ctx.get("day_usd") is not None and float(ctx["day_usd"]) >= 0.5 * BEST_DAY_GUIDE:
        out.append("best_day_cap")
    if pts < 0 and not out:
        out.append("other")
    return out


def lesson(t: dict, ctx: dict, mode: str) -> dict:
    risk, pts = _f(t.get("risk")), _f(t.get("pts"), 0.0)
    r = _f(t.get("r"))
    if r is None and risk:
        r = pts / risk
    tg = tags_of(t, ctx)
    return {"v": 1, "key": f"{mode}|{int(t['entry_t'])}|{int(t.get('dir') or 0)}", "mode": mode, "day": t.get("day"),
            "entry_t": int(t["entry_t"]), "exit_t": int(t.get("exit_t") or t["entry_t"]), "dir": int(t.get("dir") or 0),
            "risk": round(risk, 2) if risk else None, "pts": round(pts, 2), "r": round(r, 3) if r is not None else None,
            "usd": _f(t.get("usd")), "win": pts > 0, "tags": tg, "primary": tg[0] if tg else None}


def _med(xs):
    xs = [x for x in xs if x]
    return statistics.median(xs) if xs else None


def contexts(blitz: list, lit: list, news: list, prior_risks: list | None = None) -> dict:
    """entry_t -> ctx for each BLITZ trade (oldest first): the same day's LIT trades and earlier BLITZ trades, the trailing
    median stop of the 20 BLITZ trades before it (prior_risks = older stops, oldest first), the day's $ before it (usd known)."""
    by_day_lit = {}
    for le, lx, d in lit:
        by_day_lit.setdefault(d, []).append((le, lx))
    risks = list(prior_risks or [])
    out, day_prev = {}, {}
    for t in sorted(blitz, key=lambda x: int(x["entry_t"])):
        d = t.get("day")
        prev = day_prev.setdefault(d, [])
        usd = [p.get("usd") for p in prev]
        known = t.get("usd") is not None and all(u is not None for u in usd)     # $ is known on paper / live trades only
        out[int(t["entry_t"])] = {"lit": by_day_lit.get(d, []), "news": news, "prev": list(prev),
                                  "risk_med": _med(risks[-WIDE_N:]) if len(risks) >= 5 else None,
                                  "day_usd": float(sum(usd)) if known else None}      # BLITZ's own closed $ that day
        prev.append({"pts": t.get("pts"), "usd": t.get("usd"), "exit_t": t.get("exit_t")})
        risks.append(_f(t.get("risk")))
    return out


# ================================================================================================ trades in, from the PC days
def live_trades(days: list) -> tuple:
    """(blitz, lit) from engine/datapipe day bundles via engine/zeus_learn.signals, in the research shape."""
    from engine import zeus_learn as ZL
    S = ZL.signals(days)
    bl, li = [], []
    for s in S:
        if s.get("strat") == "blitz" and s.get("r") is not None and s.get("risk_pts"):
            rk = float(s["risk_pts"])
            bl.append({"day": s.get("day"), "entry_t": int(s["entry_t"]), "exit_t": int(s.get("exit_t") or s["entry_t"]),
                       "dir": s.get("dir"), "risk": rk, "pts": round(float(s["r"]) * rk, 2), "r": float(s["r"]),
                       "usd": s.get("usd"), "slip_ticks": s.get("slip_ticks"), "mode": s.get("mode") or "paper", "strat": "BLITZ"})
        elif s.get("strat") == "zlarior":
            li.append((int(s["entry_t"]), int(s.get("exit_t") or s["entry_t"]), s.get("day")))
    return bl, li


def tag_new(days: list, lessons_path: str = LESSONS, news=None) -> dict:
    """Append a lesson for every BLITZ trade in the day bundles that is not in lessons.jsonl yet. Idempotent."""
    have = read_jsonl(lessons_path)
    keys = {r.get("key") for r in have}
    bl, li = live_trades(days)
    news = news_times() if news is None else news
    old = sorted(have, key=lambda r: r.get("entry_t") or 0)
    ctx = contexts(bl, li, news, prior_risks=[r.get("risk") for r in old if r.get("entry_t", 0) < min([t["entry_t"] for t in bl] or [0])])
    new = []
    for t in sorted(bl, key=lambda x: x["entry_t"]):
        L = lesson(t, ctx[int(t["entry_t"])], t["mode"])
        if L["key"] not in keys:
            keys.add(L["key"])
            new.append(L)
    append_jsonl(lessons_path, new)
    return {"new": len(new), "total": len(have) + len(new), "losers_new": sum(1 for r in new if not r["win"])}


# ================================================================================================ 2. candidate fixes
def _f_news(ts, ctx):
    nw = ctx["news"]
    return [t for t in ts if t["strat"] != "BLITZ" or not any(int(t["entry_t"]) - NEWS_BEFORE <= n <= int(t["entry_t"]) + 30 * 60 for n in nw)]


def _f_lit_gap(ts, ctx):
    L = [t for t in ts if t["strat"] == "LIT"]
    return [t for t in ts if t["strat"] != "BLITZ" or not any(int(u["entry_t"]) <= int(t["entry_t"]) <= int(u["exit_t"]) + LIT_GAP
                                                              for u in L)]


def _f_after_loss(ts, ctx):
    out, stop = [], None
    for t in sorted(ts, key=lambda x: int(x["entry_t"])):
        if t["strat"] == "BLITZ":
            if stop is not None and int(t["entry_t"]) >= stop:
                continue
            if _f(t.get("pts"), 0.0) < 0 and stop is None:
                stop = int(t["exit_t"])
        out.append(t)
    return out


def _f_late(ts, ctx):
    return [t for t in ts if t["strat"] != "BLITZ" or _et(t["entry_t"]).hour < LATE_H]


def _f_wide(ts, ctx):
    med = ctx["risk_med"]
    return [t for t in ts if t["strat"] != "BLITZ" or not (med.get(int(t["entry_t"])) and _f(t.get("risk"), 0.0) > WIDE_X * med[int(t["entry_t"])])]


# id -> (tags it answers, words, filter(ts, ctx)): entry-time rules only (no look-ahead), testable on a trade list
CANDIDATES = {
    "no_news": (("news",), "no BLITZ entry from 15 min before to 30 min after a high-impact release", _f_news),
    "lit_gap30": (("overlap_lit",), "no BLITZ entry from a Zlarior entry to 30 min after its exit", _f_lit_gap),
    "one_loss_day": (("after_loss",), "BLITZ stops for the day after its first loser", _f_after_loss),
    "no_late": (("late_day",), "no BLITZ entry at or after 15:00 ET", _f_late),
    "no_wide": (("wide_stop",), "skip BLITZ when its stop is > 1.5x the median of its last 20 stops", _f_wide),
}
UNTESTABLE = {"chased": "needs a fill model (live fills only)", "best_day_cap": "already a guard; needs live $ to test",
              "other": "no common cause",
              "stopped_at_sweep": "true of every full stop-out by definition (it always ranks worst): descriptive only, never picked"}


def rank(lessons: list, today: str, backtest=None) -> dict:
    """Tags by NET R over the window (most negative first). backtest() -> lessons of the newest 120 sessions, used when there are
    fewer than MIN_LESSONS paper / live lessons in the window."""
    lo = (dt.date.fromisoformat(today) - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    win = [r for r in lessons if str(r.get("day") or "") >= lo and r.get("r") is not None]
    src = "paper/live lessons, last 8 weeks"
    if len(win) < MIN_LESSONS and backtest is not None:
        win, src = backtest(), "the newest 120 backtest sessions (fewer than 20 paper/live lessons yet)"
    agg = {}
    for r in win:
        for tg in r.get("tags") or []:
            a = agg.setdefault(tg, {"n": 0, "losers": 0, "net_r": 0.0})
            a["n"] += 1
            a["losers"] += 0 if r.get("win") else 1
            a["net_r"] += float(r["r"])
    rows = sorted(({"tag": k, **{kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in v.items()}} for k, v in agg.items()),
                  key=lambda x: x["net_r"])
    return {"source": src, "lessons": len(win), "tags": rows}


def pick(ranked: dict, state: dict, today: str, top: int = TOP) -> list:
    """The top tags' fixes to re-test this week: NET R < 0, n >= MIN_TAG_N, a testable fix, not rejected in the last 4 weeks,
    not already passed and waiting for the owner."""
    out = []
    for row in ranked["tags"]:
        if row["net_r"] >= 0 or row["n"] < MIN_TAG_N:
            continue
        for cid, (tags, _, _) in CANDIDATES.items():
            if row["tag"] not in tags or cid in out:
                continue
            c = (state.get("candidates") or {}).get(cid) or {}
            if c.get("status") == "passed":
                continue
            if c.get("status") == "rejected" and c.get("last_test") and \
                    (dt.date.fromisoformat(today) - dt.date.fromisoformat(c["last_test"])).days < RETRY_DAYS:
                continue
            out.append(cid)
        if len(out) >= top:
            break
    return out[:top]


# ================================================================================================ the tests
def span_eval(cids: list, ne: int = 2000, ns: int = 1000) -> dict:
    """{name: {span: {pass, fail, med_days, per_month}}} for "base" (the current live lane) and each fix, on the pre-registered
    Rapid EOD 25K book (research/pillars/blitz_rapid.py: LIT + ATLAS + BLITZ in the eval, one position, costs in)."""
    sys.path.insert(0, os.path.join(ROOT, "research", "pillars"))
    import blitz_rapid as BR  # noqa: E402
    from engine import rapid_blitz as RB
    B, R, SOA, U = BR.B, BR.R, BR.SOA, BR.U
    S = SOA.data()["S"]
    usd = float(RB.BLITZ_USD)
    names = {"base": None, **{c: CANDIDATES[c][2] for c in cids}}
    base_sp = None
    ctx = {"news": news_times(), "risk_med": {}}
    PE = {s: U.mc_paths(S, s, ne, length=R.H_EVAL, seed=7) for s in R.SPANS}
    PF = {s: U.mc_paths(S, s, ns, length=R.LEN, seed=23) for s in R.SPANS}
    out = {}
    for nm, fn in names.items():
        key = f"LEARN {nm} ${usd:.0f}"
        BR.VARS[key] = (BR.LAB, BR.LA, usd, BR.one_pos, {})
        sp = BR.build(key)
        if base_sp is None:
            base_sp = sp
            rs = []
            for ts in sp["BYe"]:
                for t in sorted(ts, key=lambda x: int(x["entry_t"])):
                    if t["strat"] == "BLITZ":
                        ctx["risk_med"][int(t["entry_t"])] = _med(rs[-WIDE_N:]) if len(rs) >= 5 else None
                        rs.append(_f(t.get("risk")))
        if fn is not None:
            sp["BYe"] = [fn(ts, ctx) for ts in sp["BYe"]]
        B.CFG.clear()
        B.CFG.update(sp["knobs"])
        r = {}
        for s in R.SPANS:
            ev = R.eval_run(sp, PE[s])
            sl = R.slot_run(sp, PF[s])
            r[s] = {**ev, "per_month": round(sl["net_6m"] / 6.0)}
        out[nm] = r
    return out


def spans_pass(base: dict, fix: dict) -> tuple:
    why = []
    for s in ("H1", "H2"):
        d_mo, d_f = fix[s]["per_month"] - base[s]["per_month"], fix[s]["fail"] - base[s]["fail"]
        if d_mo < GAIN_MO:
            why.append(f"{s} ${d_mo:+.0f}/mo < +${GAIN_MO:.0f}")
        if d_f > FAIL_PT:
            why.append(f"{s} fail {d_f:+.1f} pt > +{FAIL_PT}")
    d_mo, d_f = fix["REF"]["per_month"] - base["REF"]["per_month"], fix["REF"]["fail"] - base["REF"]["fail"]
    if d_mo < -REF_MO:
        why.append(f"2021-25 ${d_mo:+.0f}/mo")
    if d_f > REF_FAIL:
        why.append(f"2021-25 fail {d_f:+.1f} pt")
    return (not why), why


def fresh_test(cid: str, lessons: list, fresh_from: str, k: int, lit=None, news=None, seed: int = 11) -> dict:
    """The fix on paper / live BLITZ trades closed on or after fresh_from (never the data that picked it)."""
    fr = sorted((r for r in lessons if str(r.get("day") or "") >= fresh_from and r.get("r") is not None),
                key=lambda r: r["entry_t"])
    n = len(fr)
    if n < FRESH_MIN:
        return {"n": n, "pass": False, "why": f"waiting for fresh data ({n}/{FRESH_MIN} trades since {fresh_from})"}
    ts = [{"strat": "BLITZ", "entry_t": r["entry_t"], "exit_t": r["exit_t"], "pts": r["pts"], "risk": r["risk"], "day": r["day"]}
          for r in fr]
    ts += [{"strat": "LIT", "entry_t": le, "exit_t": lx, "day": d} for le, lx, d in (lit or [])]
    med, rs = {}, []
    for r in fr:
        med[r["entry_t"]] = _med(rs[-WIDE_N:]) if len(rs) >= 5 else None
        rs.append(r.get("risk"))
    ctx = {"news": news_times() if news is None else news, "risk_med": med}
    keep = set()
    by_day = {}
    for t in ts:
        by_day.setdefault(t["day"], []).append(t)
    for d, dts in by_day.items():
        keep |= {int(t["entry_t"]) for t in CANDIDATES[cid][2](dts, ctx) if t["strat"] == "BLITZ"}
    rem = [float(r["r"]) for r in fr if r["entry_t"] not in keep]
    if not rem:
        return {"n": n, "removed": 0, "pass": False, "why": "the fix removes no fresh trade"}
    mean = sum(rem) / len(rem)
    rng = random.Random(seed)
    hits = sum(1 for _ in range(BOOT) if sum(rng.choice(rem) for _ in rem) / len(rem) >= 0)
    p = (hits + 1) / (BOOT + 1)
    a = ALPHA / max(1, k)
    ok = sum(rem) < 0 and p <= a
    return {"n": n, "removed": len(rem), "removed_r": round(sum(rem), 2), "mean_r": round(mean, 3), "p": round(p, 4),
            "alpha": round(a, 4), "k": k, "pass": ok,
            "why": "passed" if ok else (f"removed trades made {sum(rem):+.1f} R" if sum(rem) >= 0 else f"p {p:.3f} > {a:.4f} (k={k})")}


# ================================================================================================ 3. card + phone line
def card_line(cid: str, base: dict, fix: dict) -> tuple:
    gain = min(fix[s]["per_month"] - base[s]["per_month"] for s in ("H1", "H2"))
    fail = fix["H1"]["fail"]
    return f"BLITZ learned {cid.replace('_', ' ')}: +${gain:,.0f}/mo, fails {fail:.1f}%", int(round(gain))


def decide_card(cid: str, base: dict, fix: dict, fresh: dict, today: str, decisions: str = DECISIONS) -> dict:
    q, gain = card_line(cid, base, fix)
    item = {"id": f"blitz-learned-{cid.replace('_', '-')}"[:40], "question": q + ". Make it a live BLITZ rule?",
            "why": f"Lessons: {CANDIDATES[cid][1]}. Passed all 3 spans and {fresh['n']} fresh trades it never saw "
                   f"(removed {fresh['removed']} trades, {fresh['removed_r']:+.1f} R, p {fresh['p']} <= {fresh['alpha']}, {fresh['k']} tests counted).",
            "impact": f"Rapid 25K eval: +${gain:,}/mo (the smaller 2026 half), eval fail {base['H1']['fail']:.1f}% -> {fix['H1']['fail']:.1f}% (Jan-Jun)",
            "impact_usd": gain, "usd_month": gain,
            "usd_month_by": {"jan_jun": fix["H1"]["per_month"] - base["H1"]["per_month"],
                             "jul_oct": fix["H2"]["per_month"] - base["H2"]["per_month"],
                             "y2021_25": fix["REF"]["per_month"] - base["REF"]["per_month"]},
            "options": ["yes", "no", "later"], "status": "open", "source": "research/blitz/learn.py (research/blitz/tests.jsonl)",
            "applies": "A yes = Claude builds it as a normal BLITZ change with proof (lit_live, update gate, red team); nothing live "
                       "changes before that", "added": today, "from": "blitz_learn"}
    doc = read_json(decisions, None)
    if not isinstance(doc, dict) or not isinstance(doc.get("items"), list):
        return {"ok": False, "why": "decisions.json missing"}
    if any(str(i.get("id")) == item["id"] for i in doc["items"]):
        return {"ok": True, "added": False, "id": item["id"], "line": q}
    doc["items"].append(item)
    doc["updated"] = today
    write_json(decisions, doc)
    return {"ok": True, "added": True, "id": item["id"], "line": q}


def phone(line: str, http=None, env=None) -> tuple:
    try:
        from tools import pc_report as PR
        cfg = PR.load_cfg(env)
        if not cfg.get("topic") or not cfg.get("on"):
            return False, "no private alert topic"
        return PR.ntfy_post(cfg["ntfy"], cfg["topic"], line, title="BLITZ learned", priority="default", tags="brain", http=http)
    except Exception as e:  # noqa: BLE001
        return False, f"{e.__class__.__name__}: {e}"[:120]


# ================================================================================================ the week
def backtest_lessons(n_sessions: int = 120) -> list:
    """Lessons of the newest backtest sessions (research shape, mode "backtest"): the ranking's fallback only."""
    sys.path.insert(0, os.path.join(ROOT, "research", "pillars"))
    import blitz_rapid as BR  # noqa: E402
    from engine import rapid_blitz as RB
    key = f"LEARN base ${float(RB.BLITZ_USD):.0f}"
    BR.VARS[key] = (BR.LAB, BR.LA, float(RB.BLITZ_USD), BR.one_pos, {})
    sp = BR.build(key)
    days = sp["BYe"][-n_sessions:]
    bl = [t for ts in days for t in ts if t["strat"] == "BLITZ"]
    li = [(int(t["entry_t"]), int(t["exit_t"]), t["day"]) for ts in days for t in ts if t["strat"] == "LIT"]
    ctx = contexts(bl, li, news_times())
    return [lesson(t, ctx[int(t["entry_t"])], "backtest") for t in bl]


def hashes(root: str = ROOT) -> dict:
    out = {}
    for rel in PROTECTED:
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                out[rel] = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            out[rel] = None
    return out


def weekly(today: str, lessons_path: str = LESSONS, tests_path: str = TESTS, state_path: str = STATE, weekly_path: str = WEEKLY,
           decisions: str = DECISIONS, evaluator=None, backtest=None, pusher=None, lit=None, news=None, ne: int = 2000,
           ns: int = 1000) -> dict:
    """The Sunday re-test (see the module doc). evaluator(cids) -> span_eval's shape; pusher(line) -> (ok, why)."""
    h0 = hashes()
    evaluator = evaluator or (lambda c: span_eval(c, ne, ns))
    backtest = backtest if backtest is not None else backtest_lessons
    pusher = pusher or phone
    L = read_jsonl(lessons_path)
    st = read_json(state_path, {}) or {}
    st.setdefault("candidates", {})
    ranked = rank(L, today, backtest)
    cids = pick(ranked, st, today)
    rep = {"day": today, "ranked": ranked, "picked": cids, "results": {}, "cards": [], "pushed": []}
    if cids:
        ev = evaluator(cids)
        base = ev["base"]
        k0 = len(read_jsonl(tests_path))
        rows = []
        for i, cid in enumerate(cids):
            c = st["candidates"].setdefault(cid, {"first_picked": today, "fresh_from": (dt.date.fromisoformat(today) + dt.timedelta(days=1)).isoformat()})
            k = k0 + i + 1
            sp_ok, sp_why = spans_pass(base, ev[cid])
            fr = fresh_test(cid, L, c["fresh_from"], k, lit=lit, news=news)
            ok = sp_ok and fr["pass"]
            res = {"cid": cid, "words": CANDIDATES[cid][1], "spans_pass": sp_ok, "spans_why": sp_why, "base": base, "fix": ev[cid],
                   "fresh": fr, "pass": ok, "k": k}
            rows.append({"v": 1, "day": today, "cid": cid, "k": k, "spans_pass": sp_ok, "fresh_pass": fr["pass"], "pass": ok,
                         "fresh_n": fr["n"], "fix": ev[cid], "base": base})
            c.update(last_test=today, tests=int(c.get("tests") or 0) + 1,
                     status="passed" if ok else ("waiting" if sp_ok and fr["n"] < FRESH_MIN else "rejected"))
            if ok:
                cd = decide_card(cid, base, ev[cid], fr, today, decisions)
                rep["cards"].append(cd)
                if cd.get("added") and cid not in (st.get("sent") or []):
                    rep["pushed"].append({"line": cd["line"], "result": list(pusher(cd["line"]))})
                    st.setdefault("sent", []).append(cid)
            rep["results"][cid] = res
        append_jsonl(tests_path, rows)
    st["last_week"] = dt.date.fromisoformat(today).isocalendar()[:2]
    st["tests_total"] = len(read_jsonl(tests_path))
    write_json(state_path, st)
    rep["tests_total"] = st["tests_total"]
    rep["protected_ok"] = hashes() == h0
    write_json(weekly_path, rep)
    return rep


def is_sunday_due(now: dt.datetime, state: dict) -> bool:
    n = now.astimezone(ET)
    return n.weekday() == 6 and list(n.date().isocalendar()[:2]) != list(state.get("last_week") or [])


def night(now: dt.datetime | None = None, days_dir: str = PC_DAYS, force_weekly: bool = False, **kw) -> dict:
    now = now or dt.datetime.now(ET)
    from engine import datapipe
    days = datapipe.load_days(days_dir, n=120) if os.path.isdir(days_dir) else []
    out = {"tag": tag_new(days, kw.get("lessons_path", LESSONS))}
    st = read_json(kw.get("state_path", STATE), {}) or {}
    if force_weekly or is_sunday_due(now, st):
        _, lit = live_trades(days) if days else ([], [])
        out["weekly"] = weekly(now.astimezone(ET).date().isoformat(), lit=lit, **kw)
    return out


def status(lessons_path: str = LESSONS, tests_path: str = TESTS, state_path: str = STATE) -> str:
    L = read_jsonl(lessons_path)
    st = read_json(state_path, {}) or {}
    rk = rank(L, dt.date.today().isoformat(), None)
    lines = [f"BLITZ lessons: {len(L)} ({sum(1 for r in L if not r.get('win'))} losers); tests run: {len(read_jsonl(tests_path))}",
             "| Tag | Trades | Losers | Net R |", "|---|---|---|---|"]
    lines += [f"| {r['tag']} | {r['n']} | {r['losers']} | {r['net_r']:+.2f} |" for r in rk["tags"]]
    for cid, c in (st.get("candidates") or {}).items():
        lines.append(f"- {cid}: {c.get('status')} (fresh from {c.get('fresh_from')}, {c.get('tests')} tests)")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("night", "tag", "weekly", "status"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--days-dir", default=PC_DAYS)
    ap.add_argument("--ne", type=int, default=2000)
    ap.add_argument("--ns", type=int, default=1000)
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args(argv)
    kw = {"ne": a.ne, "ns": a.ns}
    if a.no_push:
        kw["pusher"] = lambda line: (False, "--no-push")
    if a.cmd == "status":
        print(status())
        return 0
    if a.cmd == "tag":
        from engine import datapipe
        days = datapipe.load_days(a.days_dir, n=120) if os.path.isdir(a.days_dir) else []
        print(json.dumps(tag_new(days)))
        return 0
    if a.cmd == "weekly":
        if not a.force and not is_sunday_due(dt.datetime.now(ET), read_json(STATE, {}) or {}):
            print("weekly: not Sunday (ET) or already run this week (--force to run now)")
            return 0
        r = night(force_weekly=True, days_dir=a.days_dir, **kw)
    else:
        r = night(force_weekly=a.force, days_dir=a.days_dir, **kw)
    w = r.get("weekly") or {}
    print(f"tagged {r['tag']['new']} new BLITZ trade(s), {r['tag']['total']} lessons")
    if w:
        print(f"weekly: picked {w['picked'] or 'none'} ({w['ranked']['source']}); tests so far {w['tests_total']}; "
              f"protected files {'unchanged' if w['protected_ok'] else 'CHANGED'}")
        for cid, res in w["results"].items():
            print(f"  {cid}: {'PASS' if res['pass'] else 'no'}  spans {'ok' if res['spans_pass'] else res['spans_why']}; fresh {res['fresh']['why']}")
        for c in w["cards"]:
            print("  card:", c.get("line"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
