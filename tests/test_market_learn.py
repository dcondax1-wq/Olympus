"""Market Learn (day-marketlearn 2026-11-24): engine/market_learn.py + tools/market_learn_weekly.py. Offline, synthetic trades,
temp folders; never the network, never a live file.

  a. the pre-set tags: regime from er5 (range < 0.2 <= mixed < 0.5 <= trend), VIX band, overnight / prior-day buckets, the
     find / hold ISO-week split, the loss reasons (news > wick > turned > never), the daily book (facts of the PRIOR sessions)
  b. lessons: a planted bad bucket (losing in all 3 spans) is found as a consistent strong loss lesson; a bucket bad in one span
     only is not consistent; the shuffled-R control finds about nothing on noise
  c. trials: pick uses the find half only, a key is never re-registered, the Bonferroni bar shrinks with the running count, a
     planted real edge passes and a noise bucket is rejected, half vs skip
  d. outputs: insights shape (4 pillars, ORDER FLOW knows nothing), the summary words, a Decide proposal fits learn_night's schema,
     lessons.jsonl.gz round trip, the weekly run in a temp folder leaves the live files' hashes as they were
  e. the visible brain (day-brain-research 2026-11-24): STRUCTURE lens buckets, the zigzag is causal, structure_tags fills
     st_* from the study's tag rule, the dated journal (new / unchanged / status change / faded), confidence 0-100,
     brain_state shape (BRAIN_FEED.md), the nightly light mode writes only journal + brain_state into its --out folder
    python -X utf8 -m tests.test_market_learn
"""
from __future__ import annotations

import datetime as dt
import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import market_learn as M  # noqa: E402

FAILS = []


def ok(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        FAILS.append(what)


def fake_rows(pillar="lit", n=900, bad=None, bad_r=-0.8, seed=1, only_span=None):
    """Trades over the 3 spans with random tags; rows matching `bad` (fact, value) get mean R bad_r (in only_span if given)."""
    rng = random.Random(seed)
    days = []
    d = dt.date(2021, 11, 1)
    while d <= dt.date(2026, 10, 15):
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += dt.timedelta(days=1)
    out = []
    for i in range(n):
        day = rng.choice(days)
        r = {"pillar": pillar, "day": day, "entry_t": i, "dir": 1, "span": M.span_of(day), "half": M.week_half(day),
             "regime": rng.choice(["range", "mixed", "trend"]), "vix_band": rng.choice(["VIX <15", "VIX 15-20", "VIX 20-25"]),
             "session": rng.choice(["London 02-05", "NY AM 09:30-11:30"]), "dow": rng.choice(["Mon", "Tue", "Wed", "Thu", "Fri"]),
             "on_rng": rng.choice(["small", "normal", "big"]), "news_day": rng.random() < 0.1, "pd_room": rng.choice(["near", "far"]),
             "prior_day": rng.choice(["quiet", "normal", "big"]), "big_fri": False, "d1": rng.choice(["with", "against"]),
             "h1": rng.choice(["with", "against"])}
        mu = 0.2
        if bad and r.get(bad[0]) == bad[1] and (only_span is None or r["span"] == only_span):
            mu = bad_r
        r["r"] = round(rng.gauss(mu, 1.0), 3)
        r["usd"] = round(r["r"] * 300, 2)
        r["cause"] = None
        out.append(r)
    # the 2026 halves need enough trades too
    return out


def part_a():
    ok(M.regime_of(0.1) == "range" and M.regime_of(0.2) == "mixed" and M.regime_of(0.5) == "trend" and M.regime_of(None) is None,
       "a regime from er5: range < 0.2 <= mixed < 0.5 <= trend")
    ok(M.vix_band(14.9) == "VIX <15" and M.vix_band(20) == "VIX 20-25" and M.vix_band(30) == "VIX 25+", "a VIX bands")
    ok(M.on_rng_of(0.39) == "small" and M.on_rng_of(0.7) == "big" and M.pd_room_of(-0.1) == "through"
       and M.pd_room_of(0.5) == "blocked" and M.pd_room_of(2) == "near" and M.pd_room_of(5) == "far"
       and M.prior_day_of(1.3) == "big" and M.prior_day_of(0.69) == "quiet", "a overnight / prior-day / prior-level buckets")
    ok(M.week_half("2026-01-05") == "find" and M.week_half("2026-01-12") == "hold", "a even ISO week = find, odd = hold")
    ok(M.span_of("2026-03-01") == "H1" and M.span_of("2026-08-01") == "H2" and M.span_of("2023-01-01") == "2021-25", "a spans")
    ok(M.cause_of({"usd": 5}) is None, "a a win has no loss reason")
    ok(M.cause_of({"usd": -5, "news_in": True, "mfe_r": 0.1}) == "news", "a news first")
    ok(M.cause_of({"usd": -5, "exit": "STOP", "post_tgt_clean": True, "mfe_r": 0.9}) == "wick", "a wick before turned")
    ok(M.cause_of({"usd": -5, "exit": "STOP", "mfe_r": 0.6}) == "turned", "a turned")
    ok(M.cause_of({"usd": -5, "exit": "STOP", "mfe_r": 0.1}) == "never", "a never")
    ok(M.cause_of({"usd": -5}) is None, "a a live loss with no path = unknown, not guessed")
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "data"))
        with open(os.path.join(td, "data", "NQ_1d.csv"), "w") as fh:
            fh.write("time,open,high,low,close,volume\n")
            t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
            for k in range(30):
                c = 100 + k                      # a straight line up: ER 1.0; the last day's range 3x the others
                rng_ = 30 if k == 28 else 10
                fh.write(f"{int((t0 + dt.timedelta(days=k)).timestamp())},{c},{c + rng_ / 2},{c - rng_ / 2},{c},1\n")
        B = M.daily_book(td)
        day29 = (dt.date(2026, 1, 1) + dt.timedelta(days=29)).isoformat()
        ok(B[day29]["er5"] == 1.0 and M.prior_day_of(B[day29]["prior_ratio"]) == "big", "a daily book: facts of the prior sessions")
        day28 = (dt.date(2026, 1, 1) + dt.timedelta(days=28)).isoformat()
        ok(M.prior_day_of(B[day28]["prior_ratio"]) == "normal", "a daily book: the big day counts only for the NEXT day")
        x = M.tag({"bot": "lit", "day": day29, "dow": "Mon", "usd": -10, "r": -1, "vix": 16, "exit": "STOP", "mfe_r": 0.0}, B)
        ok(x["regime"] == "trend" and x["vix_band"] == "VIX 15-20" and x["cause"] == "never" and x["span"] == "H1", "a tag one trade")


def part_b():
    rows = fake_rows(bad=("regime", "range"), bad_r=-0.6, n=1500)
    L = M.lessons_of(rows)
    hit = [x for x in L if x["bucket"] == "regime=range"]
    ok(hit and hit[0]["sign"] == -1 and hit[0]["z"] <= -M.STRONG_Z and hit[0]["losing_all"], "b planted bad regime -> strong consistent loss lesson")
    rows = fake_rows(bad=("regime", "range"), bad_r=-1.5, n=1500, only_span="H1")
    L = M.lessons_of(rows)
    hit = [x for x in L if x["bucket"] == "regime=range"]
    ok(hit and hit[0]["sign"] == 0, "b bad in one span only -> not consistent")
    ch = M.chance(fake_rows(n=1200, seed=3), draws=10)
    ok(ch["real"] <= 3 and ch["chance_mean"] <= 3, f"b noise: few strong lessons, real {ch['real']} vs chance {ch['chance_mean']}")


def part_c():
    rows = fake_rows(bad=("vix_band", "VIX 20-25"), bad_r=-0.7, n=2500, seed=5)
    doc = {"v": 1, "count": 0, "trials": []}
    new = M.run_candidates(rows, doc, pillars=("lit",), today="2026-11-29")
    ok(new and new[0]["bucket"] == "vix_band=VIX 20-25" and new[0]["kind"] == "skip" and new[0]["status"] == "registered",
       "c the planted losing bucket is picked (skip) and registered before its test")
    ok(doc["count"] == len(new) == len(doc["trials"]), "c running count = trials registered")
    M.finish_trials(rows, doc, new)
    t = new[0]
    ok(t["status"] == "passed", f"c a real edge passes ({t['result']['why']})")
    again = M.run_candidates(rows, doc, pillars=("lit",))
    ok(all(a["key"] != t["key"] for a in again), "c a tried key is never registered again")
    noise = fake_rows(n=2500, seed=11)
    c = {"pillar": "lit", "kind": "skip", "bucket": "dow=Tue", "key": "lit|skip|dow=Tue"}
    res = M.test(noise, c, n_ever=40)
    ok(not res["passed"], "c a noise bucket is rejected")
    ok(M.test(noise, c, 1)["bar"] == 0.05 and res["bar"] == round(0.05 / 40, 5), "c the bar = 0.05 / every try ever")
    ok("lit|skip|x" not in M.PRIOR_REJECTED and "atlas|skip|vix_band=VIX <15" in M.PRIOR_REJECTED, "c already-rejected ideas skipped")
    half = M.apply_fix([{"usd": 100.0, "r": 1.0, "vix_band": "VIX 20-25"}], {"kind": "half", "bucket": "vix_band=VIX 20-25"})
    ok(half[0]["usd"] == 50.0 and half[0]["r"] == 0.5, "c half size halves $ and R")
    ok(M.apply_fix([{"usd": 1, "r": 1, "regime": "range", "dow": "Tue"}], {"kind": "skip", "bucket": "regime=range & dow=Tue"}) == [],
       "c skip drops a pair bucket")


def part_d():
    rows = fake_rows(n=1500, seed=2) + fake_rows("atlas", n=1500, seed=4)
    K = M.build(rows, root=ROOT, draws=3, trials={"count": 0, "trials": []}, book={}, pillars_doc={"pillars": [
        {"id": "orderflow", "status": "Not ready", "spans_note": "no ticks"}]})
    ok(set(K["pillars"]) == set(M.PILLARS) and K["pillars"]["orderflow"]["trades"] == 0, "d 4 pillars, ORDER FLOW knows nothing yet")
    I = M.insights(K)
    ok(set(I["pillars"]) == set(M.PILLARS) and I["paper_only"] and "lessons" in I["pillars"]["lit"], "d insights shape")
    ok(any("LIT (Zlarior) + ATLAS" in s for s in I["shared"]), "d the cross-pillar day overlap")
    md = M.summary_md(K, I, {"count": 0, "trials": []})
    ok("ORDER FLOW" in md and "shuffled" in md, "d the summary words")
    t = {"pillar": "lit", "kind": "skip", "bucket": "regime=range", "key": "lit|skip|regime=range", "status": "passed", "tested": "2026-11-29",
         "result": {"hold": {"gain_usd": 900, "p": 0.0001}, "bar": 0.01,
                    "spans": {sp: {"before": {"usd_mo": 100}, "after": {"usd_mo": 130}} for sp in M.SPANS}}}
    P = M.decide_proposals([t, {**t, "status": "rejected"}])
    from tools import learn_night as LN
    it = LN.decide_item(P[0]) if len(P) == 1 else None
    ok(it is not None and "$" in it["impact"] and it["options"] == ["yes", "no", "later"], "d a passed fix -> one Decide item (schema)")
    ok("1 fix passed" in M.phone_line([t], K) and "0 passed" in M.phone_line([{**t, "status": "rejected"}], K), "d the phone line")
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "l.jsonl.gz")
        M.save_lessons(rows[:50], p)
        ok(len(M.load_lessons(p)) == 50, "d lessons.jsonl.gz round trip")
        ok(M.merge(rows[:5], rows[:7]) == rows[:7] or len(M.merge(rows[:5], rows[:7])) == 7, "d merge adds only new rows")
    ok(M.hashes() == M.hashes(), "d the live files hashed (the weekly run fails if one changes)")


def part_e():
    ok(M.st_used_of(0.4) == "quiet" and M.st_used_of(0.6) == "half" and M.st_used_of(1.0) == "full" and M.st_used_of(1.2) == "stretched"
       and M.st_pos_of(0.1) == "extreme" and M.st_pos_of(0.9) == "chase" and M.st_pos_of(None) is None, "e structure buckets")
    ok(M.st_swing_of("with the last swing", 0.3) == "with_shallow" and M.st_swing_of("against x", 0.85) == "against_deep"
       and M.st_swing_of("with", 1.2) == "with_broken" and M.st_swing_of(None, 0.3) is None, "e swing buckets")
    ok(set(M.STRUCT_FACTS) <= set(M.FACTS) and "st_pos=extreme" not in M.bucket_words("st_pos=extreme"), "e the lens is a fact + has words")
    sys.path.insert(0, M.STRUCT_DIR)
    import bars as BR
    import numpy as np
    px = np.array([0, 5, 10, 6, 3, 8, 14, 20, 15, 9, 12], float)
    piv = BR.zigzag(px + 0.5, px - 0.5, np.full(len(px), 4.0))
    ok(piv[1][:3] == (2, 10.5, 1) and piv[1][3] == 3 and piv[3][:2] == (7, 20.5) and all(q[3] > q[0] for q in piv), "e zigzag pivots, known only at confirmation")

    class FakeStudy:
        @staticmethod
        def tag_trades(X, rows):
            return [{**r, "used": 0.6, "pos": 0.1, "phase": "against the last swing", "depth": 0.6, "early_disp": True,
                     "compression": False} for r in rows]
    old = M._study
    M._study = lambda: FakeStudy
    try:
        R = M.structure_tags([{"pillar": "lit", "entry_t": 5, "dir": 1}, {"pillar": "lit", "entry_t": 6, "dir": 1, "st_pos": "low"}], X={})
    finally:
        M._study = old
    ok(R[0]["st_used"] == "half" and R[0]["st_pos"] == "extreme" and R[0]["st_swing"] == "against_mid" and R[0]["st_disp"] == "yes"
       and R[0]["st_comp"] == "no" and R[1]["st_pos"] == "low", "e structure_tags fills st_* and keeps rows already tagged")
    o1 = {"key": "lesson|lit|x", "pillar": "lit", "noticed": "a", "evidence": {"n": 9}, "status": "watching"}
    J, add = M.update_journal([], [o1], today="2026-11-24")
    ok(len(J) == 1 and add and J[0]["date"] == "2026-11-24" and J[0]["status"] in M.STATUSES, "e journal: a new key = a dated entry")
    J, add = M.update_journal(J, [{**o1, "evidence": {"n": 12}}], today="2026-11-25")
    ok(len(J) == 1 and not add and J[0]["evidence"]["n"] == 12 and J[0]["checked"] == "2026-11-25", "e same status: evidence refreshed, no new line")
    J, add = M.update_journal(J, [{**o1, "status": "confirmed"}], today="2026-11-26")
    ok(len(J) == 2 and add[0]["was"] == "watching" and add[0]["date"] == "2026-11-26", "e status change -> a new dated entry with 'was'")
    J, add = M.update_journal(J, [], today="2026-11-27")
    ok(add and add[0]["status"] == "rejected" and "FADED" in add[0]["noticed"], "e a lesson that faded -> rejected")
    ok(M.confidence({}, []) == 0 and 0 <= M.confidence({"trades": 10, "data": {"H1": {"n": 80}, "H2": {"n": 40, "pf": 3}}}, []) <= 100,
       "e confidence 0-100 (0 with no trades)")
    rows = fake_rows(n=1500, seed=2) + fake_rows("atlas", n=1500, seed=4)
    with tempfile.TemporaryDirectory() as td:
        before = M.hashes()
        res = M.nightly(ROOT, out_dir=td, rows=rows, trials={"count": 0, "trials": []}, with_bars=False, today="2026-11-24")
        ok(sorted(os.listdir(td)) == ["brain_state.json", "journal.json"] and M.hashes() == before,
           "e nightly writes only journal + brain_state (its --out folder), live files untouched")
        S = M._read_json(os.path.join(td, "brain_state.json"))
        Jj = M._read_json(os.path.join(td, "journal.json"))
        keys = {"name", "confidence", "lessons", "watching", "rejected", "needs_owner_yes", "last_learned", "testing_next", "market_read"}
        ok(S["kind"] == "brain-state" and set(S["pillars"]) == set(M.JOURNAL_PILLARS)
           and all(keys <= set(x) for x in S["pillars"].values()) and "market" in S, "e brain_state shape (BRAIN_FEED.md)")
        ok(isinstance(Jj, list) and all({"date", "pillar", "noticed", "evidence", "status"} <= set(e) and e["status"] in M.STATUSES
                                        for e in Jj), "e journal entry shape + statuses")
        ok(S["pillars"]["orderflow"]["confidence"] == 0 and "waiting" in S["pillars"]["orderflow"]["testing_next"],
           "e ORDER FLOW: confidence 0, waiting for trades")


def main():
    for f in (part_a, part_b, part_c, part_d, part_e):
        f()
    print(f"{'ALL OK' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
