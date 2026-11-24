"""MARKET LEARN (day-marketlearn 2026-11-24; owner: every pillar - LIT, ATLAS, BLITZ, ORDER FLOW - learns the market TOGETHER,
starting from everything history already says, not from zero).

RESEARCH AND REPORTING ONLY. Nothing here trades, sizes, arms or edits a live file (live_model*.json, second_model.json,
data/account_b.json are hashed before and after a run: tools/market_learn_weekly.py refuses to finish if one changed). A fix
that passes goes to the Decide card as a question; a yes means Claude runs the full CLAUDE.md strategy-test proof first.

1. SEED. Every trade of each pillar's own backtest (tools/win_loss_anatomy.build = the repo's real backtests on futures data,
   costs in: LIT 2021-26 via lit_live, ATLAS's account units, BLITZ's live rule; 2021-25 + both 2026 halves) gets ONE context
   tag set, all known BEFORE the entry:
     regime      the prior 5 sessions' efficiency ratio of the daily closes (er5, win_loss_anatomy's own rule, set 2026-11-18):
                 range < 0.2 <= mixed < 0.5 <= trend
     vix_band    prior VIX close: <15 / 15-20 / 20-25 / 25+          session   ET session of the entry
     dow         weekday                                             on_rng    overnight range in daily ATR: small < 0.4 <= normal < 0.7 <= big
     news_day    a high-impact US release that day                   pd_room   prior-day high / low on the target side, in R:
                                                                                 through (<= 0) / blocked (< 1R) / near (1-4R) / far (4R+)
     prior_day   the prior session's range vs its 20-session ATR: quiet < 0.7 <= normal < 1.3 <= big
     big_fri     a Monday trade right after a big Friday (prior_day big + prior session a Friday)
     d1 / h1     daily / 1h trend with or against the trade
   and every loss ONE reason (win_loss_anatomy.cause_of): news / wick (shaken out, then it went our way) / turned (worked
   +0.5R first) / never (never worked). -> research/learn/lessons.jsonl.gz (one tagged trade a line).
2. LESSONS. Per pillar, every single tag bucket and the pre-set pairs (PAIRS) vs the pillar's own average R, per span. A lesson
   is CONSISTENT when the bucket is on the same side of the average in Jan-Jun 2026, Jul-Oct 2026 AND 2021-25 (MIN_N trades
   each). The honest control: the same count with R shuffled inside each span (CHANCE_DRAWS draws). SHARED lessons = a bucket
   that is consistently worse (or better) for 2+ pillars, plus the day-level overlap (days two pillars both lost).
3. WEEKLY (tools/market_learn_weekly.py, Sunday after the Friday close): the week's live / paper trades (data/pc_days via
   engine/zeus_learn.signals) are tagged and kept apart (span "live": reported, never used to pick), the seed is rebuilt,
   lessons updated, then at most MAX_CAND candidate fixes per pillar are PICKED ON THE FIND HALF ONLY (even ISO weeks),
   pre-registered in research/learn/trials.json BEFORE their test, and tested on the HOLD-OUT half (odd ISO weeks, never used
   to pick) plus each full span, at a Bonferroni bar over EVERY candidate ever registered (0.05 / running count). A candidate
   tried once is never tried again (pass or fail). Passing -> a Decide-card question + one phone line.
4. FEED: research/learn/insights.json (per pillar: top lessons, the current regime read, the last fix tried and its verdict)
   for the Brain, the Pillars page and the Research Hub; research/learn/WHAT_WE_KNOW.md in plain words.

Caveat written into every verdict: the candidate test runs on the trade list (skip / half the trades of a bucket). A one-a-day
strategy (LIT) or the ATLAS account rules could take a different trade after a skip; the full backtest re-run is the yes step.

    python -X utf8 -m engine.market_learn            # rebuild lessons + insights from research/learn/lessons.jsonl (prints)
Tests: python -X utf8 -m tests.test_market_learn
"""
from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "research", "learn")
LESSONS = os.path.join(OUT, "lessons.jsonl.gz")
KNOW = os.path.join(OUT, "knowledge.json")
INSIGHTS = os.path.join(OUT, "insights.json")
TRIALS = os.path.join(OUT, "trials.json")
SUMMARY_MD = os.path.join(OUT, "WHAT_WE_KNOW.md")
SEED_DIR = os.path.join(OUT, "seed_trades")         # raw backtest tables (gitignored, rebuilt by the weekly run)
VERSION = 1
PILLARS = ("lit", "atlas", "blitz", "orderflow")
NAME = {"lit": "LIT (Zlarior)", "atlas": "ATLAS", "blitz": "BLITZ", "orderflow": "ORDER FLOW"}
SPANS = ("H1", "H2", "2021-25")
SPAN_WORD = {"H1": "Jan-Jun 2026", "H2": "Jul-Oct 2026", "2021-25": "2021-25", "live": "live / paper"}
FACTS = ("regime", "vix_band", "session", "dow", "on_rng", "news_day", "pd_room", "prior_day", "big_fri", "d1", "h1")
PAIRS = (("regime", "vix_band"), ("regime", "prior_day"), ("regime", "session"), ("vix_band", "session"),
         ("vix_band", "prior_day"), ("regime", "on_rng"), ("vix_band", "dow"), ("prior_day", "dow"))
CAUSES = ("news", "wick", "turned", "never")
CAUSE_WORD = {"news": "news hit it", "wick": "shaken out, then it went our way", "turned": "worked first, then turned",
              "never": "never worked", None: "no path data"}
MIN_N = 8                        # trades in a bucket in EACH span before it can be a lesson
STRONG_Z = 2.0                   # |z| of the bucket's R vs the pillar average for a "strong" lesson
PICK_Z = 1.0                     # a candidate fix needs |z| >= this on the FIND half only (the hold-out + Bonferroni bar gate it)
CHANCE_DRAWS = 100
MAX_CAND = 2                     # candidate fixes per pillar a week
ALPHA = 0.05
DD_SLACK = 1.10                  # a fix may not make a span's max drawdown more than 10% deeper
PROTECTED = ("live_model.json", "live_model_lit.json", "live_model_engine.json", "second_model.json", "data/account_b.json")
KEEP = ("pillar", "source", "span", "day", "entry_t", "dir", "exit", "r", "usd", "session", "dow", "vix", "vix_band",
        "er5", "on_rng_atr", "pd_tgt_r", "news_day", "d1", "h1", "mfe_r", "mae_r", "member")
# already rejected elsewhere (docs/TESTED_AND_REJECTED.md): never re-registered here
PRIOR_REJECTED = {"atlas|skip|vix_band=VIX <15": "ATLAS VIX < 15 skip, rejected 2026-11-18 / 11-20 (payday-losses)"}


# ================================================================================================ small helpers
def _num(v):
    try:
        x = float(v)
        return x if x == x and abs(x) != float("inf") else None
    except (TypeError, ValueError):
        return None


def usd(v) -> str:
    v = round(float(v or 0))
    return "$0" if v == 0 else f"{'+' if v > 0 else '-'}${abs(v):,.0f}"


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write_json(path, obj, indent=1):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=indent, default=str)
    os.replace(tmp, path)


def hashes(root: str = ROOT) -> dict:
    out = {}
    for p in PROTECTED:
        try:
            with open(os.path.join(root, p), "rb") as fh:
                out[p] = hashlib.sha256(fh.read()).hexdigest()
        except OSError:
            out[p] = None
    return out


def week_half(day: str) -> str:
    """'find' (even ISO week) or 'hold' (odd ISO week): candidates are picked on find, tested on hold."""
    y, w, _ = dt.date.fromisoformat(str(day)[:10]).isocalendar()
    return "find" if w % 2 == 0 else "hold"


def span_of(day: str) -> str:
    d = str(day)[:10]
    return "H1" if "2026-01-01" <= d <= "2026-06-30" else "H2" if d >= "2026-07-01" else "2021-25"


# ================================================================================================ the tags (pre-set rules)
def regime_of(er5) -> str | None:
    x = _num(er5)
    if x is None:
        return None
    return "range" if x < 0.2 else "trend" if x >= 0.5 else "mixed"


def vix_band(v) -> str | None:
    v = _num(v)
    if v is None:
        return None
    return "VIX <15" if v < 15 else "VIX 15-20" if v < 20 else "VIX 20-25" if v < 25 else "VIX 25+"


def on_rng_of(x) -> str | None:
    x = _num(x)
    if x is None:
        return None
    return "small" if x < 0.4 else "big" if x >= 0.7 else "normal"


def pd_room_of(x) -> str | None:
    x = _num(x)
    if x is None:
        return None
    return "through" if x <= 0 else "blocked" if x < 1 else "near" if x < 4 else "far"


def prior_day_of(ratio) -> str | None:
    x = _num(ratio)
    if x is None:
        return None
    return "quiet" if x < 0.7 else "big" if x >= 1.3 else "normal"


def cause_of(r: dict) -> str | None:
    """One loss reason (tools/win_loss_anatomy.cause_of order: news, wick, turned, never); None = a win / no path data."""
    if (_num(r.get("usd")) or 0.0) >= 0:
        return None
    if r.get("mfe_r") is None and not r.get("news_in"):
        return None
    if r.get("news_in"):
        return "news"
    back = r.get("post_tgt_clean") if r.get("post_tgt_clean") is not None else r.get("post_1r_clean")
    if r.get("exit") in ("STOP", "CUT") and back:
        return "wick"
    if (_num(r.get("mfe_r")) or 0.0) >= 0.5:
        return "turned"
    return "never"


def daily_book(root: str = ROOT) -> dict:
    """{date: {"prior_ratio", "prior_dow", "er5"}} from data/NQ_1d.csv (all facts of the sessions BEFORE that date)."""
    import csv
    rows = []
    try:
        with open(os.path.join(root, "data", "NQ_1d.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                t = _num(r.get("time"))
                if t is None:
                    continue
                rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat(),
                             float(r["high"]), float(r["low"]), float(r["close"])))
    except OSError:
        return {}
    rows.sort()
    book = {}
    for k in range(21, len(rows) + 1):
        prev = rows[k - 1]
        rngs = [h - lo for _, h, lo, _ in rows[k - 21:k - 1]]
        atr = sum(rngs) / len(rngs) if rngs else None
        C = [c for *_, c in rows[k - 6:k]]
        path = sum(abs(C[i] - C[i - 1]) for i in range(1, len(C)))
        nxt = rows[k][0] if k < len(rows) else (dt.date.fromisoformat(prev[0]) + dt.timedelta(days=1)).isoformat()
        book[nxt] = {"prior_ratio": round((prev[1] - prev[2]) / atr, 3) if atr else None,
                     "prior_dow": dt.date.fromisoformat(prev[0]).strftime("%a"),
                     "er5": round(abs(C[-1] - C[0]) / path, 3) if path > 0 else None, "prior_day": prev[0]}
    return book


def book_for(book: dict, day: str) -> dict:
    """The facts for `day` = the book row of the first date >= day (a weekend / holiday trade takes the next session's row)."""
    if day in book:
        return book[day]
    ks = sorted(k for k in book if k >= day)
    return book[ks[0]] if ks else {}


def tag(r: dict, book: dict) -> dict:
    """One backtest (or live) trade -> the KEEP fields + every tag + its loss reason."""
    x = {k: r.get(k) for k in KEEP}
    x["pillar"] = r.get("pillar") or r.get("bot")
    x["source"] = r.get("source") or "backtest"
    x["span"] = r.get("span") if r.get("span") in SPANS or r.get("span") == "live" else span_of(r.get("day"))
    b = book_for(book, str(r.get("day"))[:10]) if book else {}
    er5 = _num(r.get("er5"))
    if er5 is None:
        er5 = _num(b.get("er5"))
        x["er5"] = er5
    x["regime"] = regime_of(er5)
    x["vix_band"] = r.get("vix_band") or vix_band(r.get("vix"))
    x["on_rng"] = on_rng_of(r.get("on_rng_atr"))
    x["pd_room"] = pd_room_of(r.get("pd_tgt_r"))
    x["prior_day"] = prior_day_of(b.get("prior_ratio"))
    x["big_fri"] = (None if not b else bool(r.get("dow") == "Mon" and b.get("prior_dow") == "Fri" and x["prior_day"] == "big"))
    x["news_day"] = r.get("news_day") if r.get("news_day") is not None else None
    x["half"] = week_half(r.get("day"))
    x["cause"] = cause_of(r)
    x["usd"] = round(float(_num(r.get("usd")) or 0.0), 2)
    x["r"] = _num(r.get("r"))
    return x


def seed_rows(seed_dir: str = SEED_DIR, root: str = ROOT, book: dict | None = None) -> list:
    """The three backtests' tables (tools/win_loss_anatomy columnar JSON) -> tagged trades."""
    book = daily_book(root) if book is None else book
    out = []
    for b in ("lit", "atlas", "blitz"):
        d = _read_json(os.path.join(seed_dir, f"trades_{b}.json"))
        if not d:
            continue
        for row in d["rows"]:
            r = dict(zip(d["cols"], row))
            r["pillar"] = b
            out.append(tag(r, book))
    return out


def live_rows(days: list, book: dict, vix: dict | None = None) -> list:
    """The PC's day folders (engine/zeus_learn.signals) -> tagged trades, span "live" (reported, never used to pick)."""
    from engine import zeus_learn as Z
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    vix = vix or {}
    out = []
    for s in Z.signals(days):
        p = {"zlarior": "lit", "atlas": "atlas", "blitz": "blitz"}.get(s.get("strat"))
        if not p:
            continue
        t = dt.datetime.fromtimestamp(int(s["entry_t"]), et)
        mod = t.hour * 60 + t.minute
        from tools.win_loss_anatomy import session_of
        v = Z.prior_vix(vix, s["day"]) if vix else None
        r = {"pillar": p, "source": s.get("mode") or "paper", "span": "live", "day": s["day"], "entry_t": s["entry_t"],
             "dir": s.get("dir"), "exit": s.get("reason"), "r": s.get("r"), "usd": s.get("usd"), "session": session_of(mod),
             "dow": t.strftime("%a"), "vix": v}
        out.append(tag(r, book))
    return out


def merge(old: list, new: list) -> list:
    """Add new rows, one per (pillar, source, entry_t, dir)."""
    seen = {(r["pillar"], r.get("source"), r.get("entry_t"), r.get("dir")) for r in old}
    out = list(old)
    for r in new:
        k = (r["pillar"], r.get("source"), r.get("entry_t"), r.get("dir"))
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def save_lessons(rows: list, path: str = LESSONS) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path + ".tmp", "wt", encoding="utf-8", compresslevel=9) as fh:
        for r in sorted(rows, key=lambda r: (r["pillar"], str(r.get("day")), r.get("entry_t") or 0)):
            fh.write(json.dumps(r, separators=(",", ":"), default=str) + "\n")
    os.replace(path + ".tmp", path)
    return path


def load_lessons(path: str = LESSONS) -> list:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return [json.loads(x) for x in fh if x.strip()]
    except (OSError, EOFError):
        return []


# ================================================================================================ stats
def agg(rows: list) -> dict:
    if not rows:
        return {"n": 0, "win": None, "avg_r": None, "pf": None, "usd": 0}
    u = [r["usd"] for r in rows]
    R = [r["r"] for r in rows if r.get("r") is not None]
    g, lo = sum(x for x in u if x > 0), -sum(x for x in u if x < 0)
    return {"n": len(rows), "win": round(100.0 * sum(1 for x in u if x > 0) / len(u), 1),
            "avg_r": round(sum(R) / len(R), 3) if R else None, "pf": round(g / lo, 2) if lo else None, "usd": round(sum(u))}


def _mean_sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return (xs[0] if xs else 0.0), 0.0
    m = sum(xs) / len(xs)
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def bucket_key(r: dict, facts) -> str | None:
    vals = []
    for f in facts:
        v = r.get(f)
        if v is None:
            return None
        vals.append(f"{f}={v}")
    return " & ".join(vals)


def cells(rows: list) -> dict:
    """{bucket: [rows]} for every single fact and every pre-set pair."""
    out = {}
    for fs in [(f,) for f in FACTS] + list(PAIRS):
        for r in rows:
            k = bucket_key(r, fs)
            if k is not None:
                out.setdefault(k, []).append(r)
    return out


def lessons_of(rows: list, half: str | None = None, min_n: int = MIN_N, R_key: str = "r") -> list:
    """Every bucket with >= min_n trades in each span: per-span delta R vs the pillar's own average there; consistent = the
    same sign in all three spans; z on the pooled rows (delta / (sd / sqrt n)). half='find' = only the find weeks."""
    rows = [r for r in rows if r.get("span") in SPANS and r.get(R_key) is not None and (half is None or r.get("half") == half)]
    base = {sp: _mean_sd([r[R_key] for r in rows if r["span"] == sp]) for sp in SPANS}
    allm, allsd = _mean_sd([r[R_key] for r in rows])
    usd_base = {sp: (sum(r["usd"] for r in rows if r["span"] == sp) / max(1, sum(1 for r in rows if r["span"] == sp))) for sp in SPANS}
    out = []
    for k, rs in cells(rows).items():
        by = {sp: [r for r in rs if r["span"] == sp] for sp in SPANS}
        if any(len(v) < min_n for v in by.values()):
            continue
        d = {sp: sum(r[R_key] for r in by[sp]) / len(by[sp]) - base[sp][0] for sp in SPANS}
        sign = 1 if all(v > 0 for v in d.values()) else -1 if all(v < 0 for v in d.values()) else 0
        sd = math.sqrt(sum(base[sp][1] ** 2 * len(by[sp]) for sp in SPANS) / len(rs)) or allsd or 1.0
        z = (sum(d[sp] * len(by[sp]) for sp in SPANS) / len(rs)) / (sd / math.sqrt(len(rs)))
        vs_avg = sum(sum(r["usd"] for r in by[sp]) - usd_base[sp] * len(by[sp]) for sp in SPANS)
        out.append({"bucket": k, "n": len(rs), "sign": sign, "z": round(z, 2),
                    "delta_r": {sp: round(d[sp], 3) for sp in SPANS},
                    "spans": {sp: agg(by[sp]) for sp in SPANS}, "usd_vs_avg": round(vs_avg),
                    "losing_all": all((agg(by[sp])["avg_r"] or 0) < 0 for sp in SPANS)})
    return sorted(out, key=lambda L: L["z"])


def strong(L: list) -> list:
    return [x for x in L if x["sign"] != 0 and abs(x["z"]) >= STRONG_Z]


def chance(rows: list, draws: int = CHANCE_DRAWS, seed: int = 7, half: str | None = None) -> dict:
    """The strong-consistent count with R (and $) shuffled across the trades of each span, the tags kept."""
    real = len(strong(lessons_of(rows, half)))
    rng = random.Random(seed)
    by = {}
    for r in rows:
        if r.get("span") in SPANS and r.get("r") is not None:
            by.setdefault(r["span"], []).append(r)
    counts = []
    for _ in range(draws):
        sh = []
        for sp, rs in by.items():
            vals = [(r["r"], r["usd"]) for r in rs]
            rng.shuffle(vals)
            sh += [{**r, "r": v[0], "usd": v[1]} for r, v in zip(rs, vals)]
        counts.append(len(strong(lessons_of(sh, half))))
    m = sum(counts) / len(counts) if counts else 0.0
    return {"real": real, "chance_mean": round(m, 1), "p": round((1 + sum(1 for c in counts if c >= real)) / (1 + len(counts)), 3),
            "draws": draws}


def cause_shares(rows: list) -> dict:
    """$-weighted share of each loss reason, per span."""
    out = {}
    for sp in list(SPANS) + ["live"]:
        L = [r for r in rows if r.get("span") == sp and r["usd"] < 0]
        tot = -sum(r["usd"] for r in L)
        if not L:
            continue
        sh = {c: round(100.0 * -sum(r["usd"] for r in L if r.get("cause") == c) / tot, 1) if tot else 0 for c in CAUSES}
        sh["unknown"] = round(100.0 * -sum(r["usd"] for r in L if r.get("cause") is None) / tot, 1) if tot else 0
        out[sp] = {"losses": len(L), "lost_usd": round(tot), "share": sh}
    return out


def overlap(rows: list, a: str, b: str) -> dict:
    """Day level: days both pillars traded, days both lost vs what independence predicts, and the daily $ correlation."""
    da, db = {}, {}
    for r in rows:
        if r.get("span") not in SPANS:
            continue
        (da if r["pillar"] == a else db if r["pillar"] == b else {}).setdefault(r["day"], 0.0)
        if r["pillar"] == a:
            da[r["day"]] += r["usd"]
        elif r["pillar"] == b:
            db[r["day"]] += r["usd"]
    both = sorted(set(da) & set(db))
    if len(both) < 20:
        return {"days": len(both)}
    la = sum(1 for d in both if da[d] < 0) / len(both)
    lb = sum(1 for d in both if db[d] < 0) / len(both)
    bl = sum(1 for d in both if da[d] < 0 and db[d] < 0)
    xa, xb = [da[d] for d in both], [db[d] for d in both]
    ma, sa = _mean_sd(xa)
    mb, sb = _mean_sd(xb)
    cor = (sum((x - ma) * (y - mb) for x, y in zip(xa, xb)) / (len(both) - 1) / (sa * sb)) if sa and sb else None
    return {"days": len(both), "both_lost": bl, "expected_if_independent": round(la * lb * len(both), 1),
            "corr": round(cor, 3) if cor is not None else None,
            "both_lost_usd": round(sum(da[d] + db[d] for d in both if da[d] < 0 and db[d] < 0))}


def shared_lessons(per: dict) -> list:
    """Buckets (single facts only) consistently worse / better for 2+ pillars."""
    idx = {}
    for p, L in per.items():
        for x in L:
            if " & " in x["bucket"] or x["sign"] == 0:
                continue
            idx.setdefault((x["bucket"], x["sign"]), []).append((p, x))
    out = []
    for (k, s), xs in idx.items():
        if len(xs) >= 2:
            out.append({"bucket": k, "sign": s, "pillars": [p for p, _ in xs],
                        "z": {p: x["z"] for p, x in xs}, "usd_vs_avg": {p: x["usd_vs_avg"] for p, x in xs},
                        "strong_in": [p for p, x in xs if abs(x["z"]) >= STRONG_Z]})
    return sorted(out, key=lambda x: (-len(x["strong_in"]), -len(x["pillars"]), sum(x["z"].values()) * x["sign"] * -1))


# ================================================================================================ candidates + the test
def trials_doc(path: str = TRIALS) -> dict:
    d = _read_json(path, None)
    if not isinstance(d, dict) or not isinstance(d.get("trials"), list):
        d = {"v": VERSION, "kind": "market-learn-trials",
             "note": "Every candidate fix ever registered (pre-registered BEFORE its test). Count = the Bonferroni divisor. A key "
                     "here is never tried again.", "count": 0, "trials": []}
    return d


def trial_key(pillar: str, kind: str, bucket: str) -> str:
    return f"{pillar}|{kind}|{bucket}"


def pick(pillar: str, rows: list, tried: set, max_n: int = MAX_CAND) -> list:
    """At most max_n candidate fixes from the FIND half only: strong consistent loss lessons whose bucket loses money in
    every span (skip) or in 2 of 3 (half size), not tried before, not already rejected elsewhere."""
    L = [x for x in lessons_of([r for r in rows if r["pillar"] == pillar], half="find") if x["sign"] < 0 and x["z"] <= -PICK_Z]
    out = []
    for x in L:
        neg = sum(1 for sp in SPANS if (x["spans"][sp]["avg_r"] or 0) < 0)
        kind = "skip" if neg == 3 else "half" if neg == 2 else None
        if kind is None:
            continue
        key = trial_key(pillar, kind, x["bucket"])
        if key in tried or key in PRIOR_REJECTED:
            continue
        out.append({"key": key, "pillar": pillar, "kind": kind, "bucket": x["bucket"], "find_z": x["z"], "find_n": x["n"]})
        if len(out) >= max_n:
            break
    return out


def _in(r: dict, bucket: str) -> bool:
    for part in bucket.split(" & "):
        f, v = part.split("=", 1)
        if str(r.get(f)) != v:
            return False
    return True


def apply_fix(rows: list, c: dict) -> list:
    """The trade list with the fix: skip = the bucket's trades dropped, half = their $ and R halved."""
    out = []
    for r in rows:
        if _in(r, c["bucket"]):
            if c["kind"] == "skip":
                continue
            r = {**r, "usd": r["usd"] * 0.5, "r": (r["r"] or 0) * 0.5}
        out.append(r)
    return out


def span_metrics(rows: list) -> dict:
    rows = sorted(rows, key=lambda r: (str(r["day"]), r.get("entry_t") or 0))
    a = agg(rows)
    if not rows:
        return {**a, "tpw": 0, "usd_mo": 0, "maxdd": 0}
    d0, d1 = dt.date.fromisoformat(rows[0]["day"][:10]), dt.date.fromisoformat(rows[-1]["day"][:10])
    weeks = max(1.0, ((d1 - d0).days + 1) / 7.0)
    eq = pk = dd = 0.0
    for r in rows:
        eq += r["usd"]
        pk = max(pk, eq)
        dd = min(dd, eq - pk)
    return {**a, "tpw": round(a["n"] / weeks, 2), "usd_mo": round(a["usd"] / (weeks / 4.345)), "maxdd": round(dd)}


def _phi(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def hold_test(rows: list, c: dict) -> dict:
    """Hold-out half: the fix's $ gain, and how unusual it is vs the same fix on a random set of the same size (one-sided p)."""
    H = [r for r in rows if r.get("half") == "hold" and r.get("span") in SPANS]
    S = [r for r in H if _in(r, c["bucket"])]
    k, N = len(S), len(H)
    w = 1.0 if c["kind"] == "skip" else 0.5
    gain = -w * sum(r["usd"] for r in S)
    if k == 0 or N < 3 or k >= N:
        return {"n": N, "k": k, "gain_usd": round(gain), "z": None, "p": 1.0}
    mu, sd = _mean_sd([r["usd"] for r in H])
    var = (w ** 2) * k * sd ** 2 * (N - k) / (N - 1)
    z = (gain - (-w * k * mu)) / math.sqrt(var) if var > 0 else 0.0
    return {"n": N, "k": k, "gain_usd": round(gain), "z": round(z, 2), "p": round(1 - _phi(z), 5)}


def test(rows: list, c: dict, n_ever: int) -> dict:
    """The pre-registered test. PASS = hold-out gain > 0 at p <= ALPHA / n_ever AND, in each full span: net $ not lower, PF not
    lower, max drawdown not more than 10% deeper, trades a week not below min(2, today's)."""
    P = [r for r in rows if r["pillar"] == c["pillar"] and r.get("span") in SPANS]
    hold = hold_test(P, c)
    bar = ALPHA / max(1, n_ever)
    spans, why = {}, []
    for sp in SPANS:
        b = span_metrics([r for r in P if r["span"] == sp])
        n = span_metrics(apply_fix([r for r in P if r["span"] == sp], c))
        spans[sp] = {"before": b, "after": n}
        w = SPAN_WORD[sp]
        if n["usd"] < b["usd"]:
            why.append(f"{w} net {usd(n['usd'] - b['usd'])}")
        if (n["pf"] or 0) < (b["pf"] or 0):
            why.append(f"{w} PF {b['pf']} -> {n['pf']}")
        if n["maxdd"] < b["maxdd"] * DD_SLACK:
            why.append(f"{w} max DD {usd(b['maxdd'])} -> {usd(n['maxdd'])}")
        if n["tpw"] < min(2.0, b["tpw"]):
            why.append(f"{w} {n['tpw']} trades a week")
    if hold["gain_usd"] <= 0:
        why.insert(0, f"hold-out weeks {usd(hold['gain_usd'])}")
    elif hold["p"] > bar:
        why.insert(0, f"hold-out p {hold['p']} > bar {bar:.4f} (0.05 / {n_ever} tries)")
    return {"passed": not why, "why": why, "hold": hold, "bar": round(bar, 5), "spans": spans,
            "caveat": "trade-list test: a full backtest re-run is the yes step"}


def run_candidates(rows: list, doc: dict, pillars=("lit", "atlas", "blitz"), today: str | None = None) -> list:
    """Pick, PRE-REGISTER (written to doc before any test), then test. Mutates doc; returns this run's trials."""
    today = today or dt.date.today().isoformat()
    tried = {t["key"] for t in doc["trials"]}
    new = []
    for p in pillars:
        for c in pick(p, rows, tried):
            doc["count"] += 1
            t = {**c, "registered": today, "n_at_registration": doc["count"], "status": "registered",
                 "plan": "hold-out odd ISO weeks + each full span; Bonferroni 0.05 / running count"}
            doc["trials"].append(t)
            tried.add(c["key"])
            new.append(t)
    return new


def finish_trials(rows: list, doc: dict, new: list) -> list:
    for t in new:
        res = test(rows, t, doc["count"])
        t.update(status="passed" if res["passed"] else "rejected", tested=dt.date.today().isoformat(), result=res)
    return new


# ================================================================================================ words
def bucket_words(b: str) -> str:
    W = {"regime=range": "range weeks (choppy 5 days)", "regime=trend": "trending weeks", "regime=mixed": "mixed weeks",
         "prior_day=big": "after a big day", "prior_day=quiet": "after a quiet day", "prior_day=normal": "after a normal day",
         "big_fri=True": "Mondays after a big Friday", "news_day=True": "news days", "news_day=False": "no-news days",
         "on_rng=small": "a small overnight range", "on_rng=big": "a big overnight range", "on_rng=normal": "a normal overnight",
         "pd_room=blocked": "the prior-day level under 1R ahead", "pd_room=through": "already past the prior-day level",
         "pd_room=near": "the prior-day level 1-4R ahead", "pd_room=far": "the prior-day level 4R+ ahead",
         "d1=against": "against the daily trend", "d1=with": "with the daily trend",
         "h1=against": "against the 1h trend", "h1=with": "with the 1h trend"}
    out = []
    for part in b.split(" & "):
        f, v = part.split("=", 1)
        out.append(W.get(part) or (v if f in ("vix_band", "session") else DOW.get(v, v) if f == "dow" else part))
    return " + ".join(out)


DOW = {"Mon": "Mondays", "Tue": "Tuesdays", "Wed": "Wednesdays", "Thu": "Thursdays", "Fri": "Fridays", "Sun": "Sunday nights"}


def by_fact(P: list, f: str) -> dict:
    """avg R per span for each value of one fact (the plain table under the lessons)."""
    vals = sorted({r.get(f) for r in P if r.get(f) is not None}, key=str)
    return {str(v): {sp: agg([r for r in P if r.get(f) == v and r.get("span") == sp]) for sp in SPANS} for v in vals}


def lesson_line(p: str, x: dict) -> str:
    s = x["spans"]
    verb = "loses" if x["losing_all"] else "does worse" if x["sign"] < 0 else "does best"
    return (f"{NAME[p]} {verb} when: {bucket_words(x['bucket'])}. Avg R {s['H1']['avg_r']} / {s['H2']['avg_r']} / "
            f"{s['2021-25']['avg_r']} (Jan-Jun / Jul-Oct / 2021-25, {x['n']} trades), {usd(x['usd_vs_avg'])} vs a normal trade, "
            f"z {x['z']}{'' if abs(x['z']) >= STRONG_Z else ' (weak)'}")


# ================================================================================================ the build
def current_read(book: dict, root: str = ROOT) -> dict:
    """Today's tags from the newest daily bars + VIX close (what next week walks into)."""
    import csv
    if not book:
        return {}
    k = max(book)
    b = book[k]
    v = None
    try:
        with open(os.path.join(root, "data", "VIX_1d.csv"), encoding="utf-8") as fh:
            last = list(csv.DictReader(fh))[-1]
            v, vday = _num(last.get("close")), last.get("date")
    except (OSError, IndexError):
        vday = None
    return {"for": k, "data_to": b.get("prior_day"), "regime": regime_of(b.get("er5")), "er5": b.get("er5"),
            "prior_day": prior_day_of(b.get("prior_ratio")), "vix": v, "vix_day": vday, "vix_band": vix_band(v)}


def read_vs_history(rows: list, p: str, cur: dict) -> dict | None:
    """The pillar's history in today's regime + VIX band."""
    if not cur.get("regime") or not cur.get("vix_band"):
        return None
    P = [r for r in rows if r["pillar"] == p and r.get("span") in SPANS]
    S = [r for r in P if r.get("regime") == cur["regime"] and r.get("vix_band") == cur["vix_band"]]
    if not P:
        return None
    a, base = agg(S), agg(P)
    return {"bucket": f"regime={cur['regime']} & vix_band={cur['vix_band']}", "n": a["n"], "avg_r": a["avg_r"],
            "pf": a["pf"], "base_avg_r": base["avg_r"],
            "spans": {sp: agg([r for r in S if r["span"] == sp]) for sp in SPANS}}


def build(rows: list, root: str = ROOT, draws: int = CHANCE_DRAWS, trials: dict | None = None, book: dict | None = None,
          pillars_doc: dict | None = None) -> dict:
    """lessons.jsonl rows -> the full knowledge doc (per pillar + shared + the control)."""
    book = daily_book(root) if book is None else book
    cur = current_read(book, root)
    trials = trials or trials_doc()
    per, out = {}, {"v": VERSION, "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "paper_only": True,
                    "pillars": {}, "current": cur}
    pdoc = pillars_doc if pillars_doc is not None else (_read_json(os.path.join(root, "research", "lab", "pillars.json"), {}) or {})
    for p in PILLARS:
        P = [r for r in rows if r["pillar"] == p]
        if not P:
            of = next((x for x in pdoc.get("pillars", []) if x.get("id") == p), {})
            out["pillars"][p] = {"name": NAME[p], "trades": 0, "knows": "nothing yet: no trades to learn from",
                                 "status": of.get("status"), "prior": of.get("spans_note")}
            continue
        L = lessons_of(P)
        per[p] = L
        st = strong(L)
        ch = chance(P, draws=draws) if draws else None
        live = [r for r in P if r.get("span") == "live"]
        mine = [t for t in trials["trials"] if t["pillar"] == p]
        out["pillars"][p] = {
            "name": NAME[p], "trades": sum(1 for r in P if r.get("span") in SPANS), "live_trades": len(live),
            "data": {sp: span_metrics([r for r in P if r["span"] == sp]) for sp in SPANS},
            "first_day": min(r["day"] for r in P), "last_day": max(r["day"] for r in P),
            "causes": cause_shares(P), "chance": ch,
            "worst": [x for x in L if x["sign"] < 0][:5], "best": sorted([x for x in L if x["sign"] > 0], key=lambda x: -x["z"])[:3],
            "strong_n": len(st), "by": {f: by_fact(P, f) for f in ("regime", "vix_band", "prior_day")},
            "live": agg(live) if live else None, "read": read_vs_history(rows, p, cur),
            "last_fix": ({k: mine[-1].get(k) for k in ("key", "kind", "bucket", "status", "registered", "tested")}
                         | {"why": (mine[-1].get("result") or {}).get("why")}) if mine else None}
    out["shared"] = shared_lessons(per)[:8]
    out["overlap"] = {f"{a}+{b}": overlap(rows, a, b) for a, b in (("lit", "atlas"), ("lit", "blitz"), ("atlas", "blitz"))}
    return out


def knows_words(K: dict, p: str) -> list:
    x = K["pillars"][p]
    if not x.get("trades"):
        return [f"{x['name']}: knows nothing yet. {x.get('status') or ''}".strip(), f"Prior from bar proxies: {x.get('prior')}"]
    lines = []
    ch = x.get("chance") or {}
    c = x["causes"]
    for sp in SPANS:
        if sp in c:
            s = c[sp]["share"]
            lines.append(f"Losses {SPAN_WORD[sp]} ({c[sp]['losses']} trades, {usd(-c[sp]['lost_usd'])}): never worked {s['never']}%, "
                         f"worked then turned {s['turned']}%, shaken out {s['wick']}%, news {s['news']}%")
    lines.append(f"Strong lessons (same side in all 3 spans, |z| >= {STRONG_Z}): {ch.get('real')} found vs "
                 f"{ch.get('chance_mean')} with the results shuffled (p {ch.get('p')})"
                 + (" - no better than chance, read them as hints" if (ch.get('p') or 1) > 0.05 else ""))
    for f in ("regime", "vix_band"):
        t = x["by"][f]
        lines.append(f"By {'regime' if f == 'regime' else 'VIX'} (avg R Jan-Jun / Jul-Oct / 2021-25): " + "; ".join(
            f"{v} {t[v]['H1']['avg_r']} / {t[v]['H2']['avg_r']} / {t[v]['2021-25']['avg_r']}" for v in t))
    for w in x["worst"][:3]:
        lines.append(lesson_line(p, w))
    for b in x["best"][:2]:
        lines.append(lesson_line(p, b))
    return lines


def insights(K: dict) -> dict:
    """The compact feed (Brain / Pillars / Research Hub)."""
    out = {"v": VERSION, "kind": "market-learn-insights", "built": K["built"], "paper_only": True,
           "note": "What the market taught us. Research only: nothing here changes a live rule. A fix that passes goes to the "
                   "Decide card.", "current": K["current"], "pillars": {}, "shared": []}
    for p, x in K["pillars"].items():
        if not x.get("trades"):
            out["pillars"][p] = {"name": x["name"], "lessons": [], "read": None, "last_fix": None, "knows": x.get("knows"),
                                 "prior": x.get("prior")}
            continue
        r = x.get("read")
        rw = None
        if r and r["n"]:
            rw = (f"{bucket_words(r['bucket'])}: {r['n']} past trades, avg R {r['avg_r']} vs {r['base_avg_r']} overall")
        ch = x.get("chance") or {}
        out["pillars"][p] = {"name": x["name"], "trades": x["trades"], "live_trades": x["live_trades"],
                             "lessons": [lesson_line(p, w) for w in x["worst"][:3]] + [lesson_line(p, b) for b in x["best"][:1]],
                             "chance": f"{ch.get('real')} strong lessons vs {ch.get('chance_mean')} by chance (p {ch.get('p')})",
                             "losses": x["causes"], "read": rw, "last_fix": x.get("last_fix")}
    for s in K["shared"][:5]:
        out["shared"].append(f"{' and '.join(NAME[p] for p in s['pillars'])} both do "
                             f"{'worse' if s['sign'] < 0 else 'better'} in {bucket_words(s['bucket'])} "
                             f"(z {', '.join(f'{NAME[p]} {z}' for p, z in s['z'].items())})")
    for k, o in K["overlap"].items():
        if o.get("days", 0) >= 20:
            a, b = k.split("+")
            out["shared"].append(f"{NAME[a]} + {NAME[b]}: {o['days']} days both traded, both lost on {o['both_lost']} "
                                 f"({o['expected_if_independent']} if unrelated), daily $ correlation {o['corr']}")
    return out


def summary_md(K: dict, I: dict, trials: dict) -> str:
    L = ["# What each pillar has learned so far", "",
         f"Built {K['built']} by `engine/market_learn.py` from {sum(x.get('trades', 0) for x in K['pillars'].values())} backtest "
         f"trades (the repo's own backtests on NQ futures data, costs in) + live / paper rows. Research only: nothing live changes.",
         "",
         "How to read it: a lesson is a context bucket where the pillar did worse (or better) than its own average in ALL THREE "
         "spans (Jan-Jun 2026, Jul-Oct 2026, 2021-25). The chance line says how many such lessons you get with the results "
         "shuffled at random - if the real count is not clearly above it, the lessons are hints, not an edge.", ""]
    cur = K.get("current") or {}
    L += [f"**Now** (after the {cur.get('data_to')} close): {cur.get('regime')} regime (5-day ER {cur.get('er5')}), prior day {cur.get('prior_day')}, "
          f"{cur.get('vix_band')} (VIX {cur.get('vix')} on {cur.get('vix_day')}).", ""]
    for p in PILLARS:
        L.append(f"## {NAME[p]}")
        L += [f"- {s}" for s in knows_words(K, p)]
        r = (I["pillars"].get(p) or {}).get("read")
        if r:
            L.append(f"- Today's read: {r}")
        L.append("")
    L.append("## Shared (cross-pillar)")
    L += [f"- {s}" for s in I["shared"]] or ["- nothing shared yet"]
    L += ["", f"## Fixes tried ({trials['count']} ever registered; bar = 0.05 / that count)"]
    for t in trials["trials"][-12:]:
        res = t.get("result") or {}
        L.append(f"- {t['registered']} {NAME[t['pillar']]} {t['kind']} {bucket_words(t['bucket'])}: **{t['status']}**"
                 + (f" ({'; '.join(res.get('why') or [])})" if res.get("why") else
                    f" (hold-out {usd((res.get('hold') or {}).get('gain_usd'))}, p {(res.get('hold') or {}).get('p')})" if res else ""))
    if not trials["trials"]:
        L.append("- none yet")
    return "\n".join(L) + "\n"


def decide_proposals(new: list) -> list:
    """Passed trials -> learn_night.step_decide proposals (a yes = run the full proof, never a live change by itself)."""
    out = []
    for t in new:
        if t.get("status") != "passed":
            continue
        res = t["result"]
        d = {sp: res["spans"][sp]["after"]["usd_mo"] - res["spans"][sp]["before"]["usd_mo"] for sp in SPANS}
        pid = ("ml-" + t["pillar"] + "-" + t["kind"] + "-" + hashlib.sha1(t["key"].encode()).hexdigest()[:8])
        out.append({"id": pid, "bot": t["pillar"], "day": t.get("tested"),
                    "question": f"{NAME[t['pillar']]}: {t['kind']} trades in {bucket_words(t['bucket'])}? Let Claude run the full proof?",
                    "why": (f"Market Learn found it on the find weeks and it held on the hold-out weeks ({usd(res['hold']['gain_usd'])}, "
                            f"p {res['hold']['p']} under the bar {res['bar']}) and in all 3 spans. Trade-list test only."),
                    "impact": (f"{usd(d['H1'])} / {usd(d['H2'])} / {usd(d['2021-25'])} a month (Jan-Jun / Jul-Oct / 2021-25) on the "
                               f"trade list; $0 changes before a yes.")})
    return out


def phone_line(new: list, K: dict) -> str:
    ok = [t for t in new if t.get("status") == "passed"]
    if ok:
        return (f"Market Learn: {len(ok)} fix{'es' if len(ok) > 1 else ''} passed - "
                + "; ".join(f"{NAME[t['pillar']]} {t['kind']} {bucket_words(t['bucket'])}" for t in ok) + ". On the Decide card.")
    return f"Market Learn: {len(new)} fix{'es' if len(new) != 1 else ''} tested, 0 passed. Nothing to decide; lessons updated."


def main(argv=None) -> int:
    rows = load_lessons()
    if not rows:
        print("no research/learn/lessons.jsonl.gz yet: python -X utf8 tools/market_learn_weekly.py --seed")
        return 1
    K = build(rows, draws=20)
    for p in PILLARS:
        print(f"== {NAME[p]}")
        for s in knows_words(K, p):
            print("  " + s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
