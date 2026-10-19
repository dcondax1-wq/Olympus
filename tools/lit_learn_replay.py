"""The LIT learning loop on history: what engine/lit_learn.py would have learned, and whether it would have helped.

Replays 2026 as if the learner had run every Sunday from Feb 1 (each review sees only the trades that finished before that
Sunday), applies the knobs of each week to the next week's trades, and scores the result against fixed LIT on the real
eval path (tools/lit_select.py: the candidate replay == run lit_live trade for trade, eval sizing $800 up to a 25-pt stop
x the weekly stop, one rounding with the learned multiplier, a size-up never risks more than $900, the 60% room cap, MFFU
50K evals back to back, a fresh eval on every session for the odds). The same on 2021-25 (5m entries only) as a stress
reference: journal from 2021-11, reviews every Sunday from 2022-01-02.

    python tools/lit_learn_replay.py run       # both replays -> research/lit/learn_replay.json, run lit_learn_replay
    python tools/lit_learn_replay.py seed      # data/lit_journal.jsonl (2026 backtest records) + data/lit_learning.json
Judged like every LIT change (owner 2026-10-18): better in 2026 H1 AND H2 at 2-4 trades a week, eval 2-week fails not up;
2021-25 is a reference line. If the learned version is not better on both halves it ships in observe mode. 1 process.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit_learn as LL  # noqa: E402
from tools import lit_select as S  # noqa: E402
from tools import lit_select_rules as SR  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "learn_replay.json")
SP = ("H1", "H2", "2026", "2021-25")


def base_path():
    R = S.build()["rows"]
    U = S.replay(R)                          # LIT live, one trade a day, weekly-stop marks (wk_m)
    M = S.base()[0]
    return R, U, M


def journal(U, M):
    """Journal records of the fixed-LIT path (what the journal records regardless of size: the model's trades)."""
    out = []
    for t in U:
        z = t["_row"]["z"]
        f = dict(t["_row"]["f"])
        f.update(LL.h4_feats(M, int(z["i"]), int(z["dir"])))
        post = LL.post_facts(M, {"dir": t["dir"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "target_px": t["target_px"],
                                 "day": t["day"]})
        out.append(LL.record(t, "backtest", f=f, post=post, logged_at=int(t["exit_t"])))
    return out


def sundays(a, z):
    d = dt.date.fromisoformat(a)
    d += dt.timedelta(days=(6 - d.weekday()) % 7)
    out = []
    while d.isoformat() <= z:
        out.append(d.isoformat())
        d += dt.timedelta(days=7)
    return out


def learn(recs, sun, start_day, quiet=False):
    """The learner every Sunday (mode apply, so the knobs evolve as if live). Returns ({sunday: knobs in force after its
    review}, [decisions], final state)."""
    L = LL.default_learning("apply")
    R = [r for r in recs if r["day"] >= start_day]
    sess = [d for d in S.SESS if d >= start_day]
    K, D = {}, []
    t0 = time.time()
    import collections
    FC = collections.Counter()
    for s in sun:
        L, d = LL.review(R, L, s, sessions=sess, source="history replay")
        K[s] = copy.deepcopy(L["knobs"])
        props = (L.get("last_review") or {}).get("proposals") or []
        d["proposals"] = len(props)
        d["passed"] = sum(1 for p in props if p["pass"])
        for p in props:
            FC["proposals"] += 1
            for f in p["failed"]:
                FC[f] += 1
        D.append(d)
        if d["action"] != "none" and not quiet:
            print(f"  {s}: {d['action']} {d['fam']}/{d['bucket']} {d['before']} -> {d['after']} | {d['reason'][:150]}", flush=True)
    L["_fail_counts"] = dict(FC)
    if not quiet:
        print(f"  {len(sun)} reviews in {time.time() - t0:.0f}s, {sum(1 for d in D if d['action'] != 'none')} changes", flush=True)
    return K, D, L


def sized_path(U, recs, K):
    """U with each trade's learned multiplier (g_m) from the last review before its day; skipped trades removed (the
    weekly-stop marks stay as the model counted them: a skipped trade is still the model's trade)."""
    by_key = {r["key"]: r for r in recs}
    suns = sorted(K)
    out, n_ch = [], 0
    for t in U:
        prev = [s for s in suns if s < t["day"]]
        x = dict(t)
        x["g_m"] = 1.0
        if prev:
            r = by_key[f"{t['day']}|{int(t['entry_t'])}|{int(t['dir'])}"]
            m, skip, _ = LL.mult_of(r["buckets"], K[prev[-1]])
            if skip:
                n_ch += 1
                continue
            x["g_m"] = float(m)
            n_ch += abs(m - 1.0) > 1e-9
        out.append(x)
    return out, n_ch


def score(U):
    o = S.score(U, spans=SP)
    fu = SR.funded(U, spans=SP)
    for s in o:
        o[s]["funded_net"] = fu[s]["net"]; o[s]["funded_pf"] = fu[s]["pf"]; o[s]["funded_dd"] = fu[s]["dd"]
    return o


KEYS = ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "dec10", "p15", "f15", "p20", "f20", "pass_rate",
        "pass_med", "slow_pass", "b2b", "funded_net", "funded_pf", "funded_dd")


def compact(o):
    return {s: {k: o[s].get(k) for k in KEYS} for s in o}


def run(save=True):
    R, U, M = base_path()
    recs = journal(U, M)
    print("journal records", len(recs), "2026", sum(r["day"] >= "2026" for r in recs))
    base = score(U)
    print("BASE (fixed LIT, eval sizing)")
    for s in SP:
        print("  " + S.line(base, s), "| funded", base[s]["funded_net"])
    print("2026 learner (Sundays from 2026-02-01, journal from 2026-01-02)")
    K26, D26, L26 = learn(recs, sundays("2026-02-01", "2026-10-18"), "2026-01-01")
    print("2021-25 learner (Sundays from 2022-01-02, journal from 2021-11)")
    K21, D21, L21 = learn(recs, sundays("2022-01-02", "2025-12-28"), "2021-01-01")
    K = {**K21, **K26}
    U2, n_ch = sized_path([t for t in U], recs, K)
    lrn = score(U2)
    print(f"LEARNED ({n_ch} trades re-sized or skipped)")
    for s in SP:
        print("  " + S.line(lrn, s), "| funded", lrn[s]["funded_net"],
              f"(d net {lrn[s]['net'] - base[s]['net']:+,}, funded {lrn[s]['funded_net'] - base[s]['funded_net']:+,})")
    # "better" in a half = more money on the eval path AND at the funded size (the steadier yardstick: no eval-path luck),
    # 2-week eval fails not up, 2-week passes not down, 2+ trades a week
    def chk(s):
        x, y = lrn[s], base[s]
        return {"net": x["net"] > y["net"], "funded": x["funded_net"] > y["funded_net"], "f10": x["f10"] <= y["f10"],
                "p10": x["p10"] >= y["p10"], "tpw": x["tpw"] >= 2.0}
    checks = {s: chk(s) for s in SP}
    better = {s: all(checks[s].values()) for s in SP}
    both = better["H1"] and better["H2"]
    mode = "apply" if both else "observe"
    miss = "; ".join(f"{s}: " + ", ".join(k for k, v in checks[s].items() if not v) for s in ("H1", "H2") if not better[s])
    verdict = ("better on both 2026 halves (eval-path $ and funded $ up, 2-week fails not up, 2-week passes not down, 2+ trades "
               "a week): ships in APPLY mode" if both else
               f"not better on both 2026 halves ({miss}): ships in OBSERVE mode (logs proposals, applies nothing)")
    print("VERDICT:", verdict)
    # causes of the 2026 losses (the journal's anatomy)
    import collections
    cz = collections.defaultdict(lambda: [0, 0.0])
    for r in recs:
        if r["day"] >= "2026" and r["cause"]:
            cz[r["cause"]][0] += 1; cz[r["cause"]][1] += r["pnl"]
    tags = collections.Counter(t for r in recs if r["day"] >= "2026" for t in r["tags"])
    out = {"built": dt.datetime.now().isoformat(timespec="seconds"), "verdict": verdict, "mode": mode, "better": better,
           "checks": checks, "z_min": LL.Z_MIN,
           "base": compact(base), "learned": compact(lrn), "resized": n_ch,
           "decisions_2026": [{k: d.get(k) for k in ("id", "asof", "action", "fam", "bucket", "before", "after", "reason")} for d in D26],
           "decisions_2021_25": [{k: d.get(k) for k in ("id", "asof", "action", "fam", "bucket", "before", "after", "reason")}
                                 for d in D21 if d["action"] != "none"],
           "reviews_2026": len(D26), "changes_2026": sum(1 for d in D26 if d["action"] != "none"),
           "reviews_2021_25": len(D21), "changes_2021_25": sum(1 for d in D21 if d["action"] != "none"),
           "knobs_end_2026": K26[max(K26)] if K26 else {}, "knobs_end_2025": K21[max(K21)] if K21 else {},
           "last_review_2026": L26.get("last_review"),
           "guardrail_fails_2026": L26.pop("_fail_counts", {}), "guardrail_fails_2021_25": L21.pop("_fail_counts", {}),
           "proposals_by_week_2026": [[d["asof"], d.get("proposals"), d.get("passed")] for d in D26],
           "causes_2026": {c: {"n": v[0], "usd_at_eval_base": round(v[1], 2), "label": LL.CAUSES[c]} for c, v in
                           sorted(cz.items(), key=lambda kv: kv[1][1])},
           "tags_2026": dict(tags.most_common())}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    print("->", OUT)
    if save:
        _save(U2, lrn, base, verdict, mode)
    return out, recs, L26


def _save(U2, o, b, verdict, mode):
    T = S.evals_x(U2, "2026")[1] + S.evals_x(U2, "2021-25")[1]
    T = [{k: v for k, v in t.items() if k not in ("legs", "_row")} for t in T]
    Sc = S.rl.score(T, S.SESS)

    def h(s):
        x = o[s]
        return (f"n={x['n']} {x['tpw']}/wk win {x['win']}% PF {x['pf']} net {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,}; "
                f"eval 2wk {x['p10']}/{x['f10']} (dec10 {x['dec10']}), 3wk {x['p15']}/{x['f15']}, 1mo {x['p20']}/{x['f20']}, pass rate "
                f"{x['pass_rate']}%, median {x['pass_med']} sessions, slow_pass {x['slow_pass']}%; funded {x['funded_net']:+,} "
                f"(base {b[s]['funded_net']:+,}, eval-path base {b[s]['net']:+,})")
    S.rl.save("lit_learn_replay", "Learning loop: bounded bucket sizing re-learned every Sunday (walk-forward, guardrails)",
              "other", "Owner order 2026-10-18: the bot must learn from its losses and change, without overfitting or "
              "blowing the eval.", params={**S.LIVE, "size": list(S.EVAL_RULE), "room_k": S.ROOM_K,
                                           "learner": LL.default_learning()["rules"]},
              trades=T, scored=Sc, status="adopt-candidate" if mode == "apply" else "info",
              verdict=f"{verdict}. 2026 H1 {h('H1')}. 2026 H2 {h('H2')}. 2021-25 reference {h('2021-25')}.",
              notes="tools/lit_learn_replay.py + engine/lit_learn.py: knobs of each Sunday's review applied to the next week's "
                    "trades (only trades that finished before the Sunday). Eval sizing $800/25 + weekly stop + learned "
                    "multiplier in one rounding, $900 risk cap on a size-up, 60% room cap; MFFU 50K back to back.",
              writeup="lit-learning-loop", tags=["lit", "lit_learn"])
    print("  saved run lit_learn_replay")


def seed(mode=None, recs=None, L26=None):
    """data/lit_journal.jsonl: the 2026 backtest records (append-only; existing keys are kept). data/lit_learning.json: the
    learner's state after the reviews of 2026 (the shadow knobs) in the shipped mode, with the replay summary."""
    rep = json.load(open(OUT))
    if recs is None or L26 is None:
        R, U, M = base_path()
        recs = journal(U, M)
        _, _, L26 = learn(recs, sundays("2026-02-01", "2026-10-18"), "2026-01-01", quiet=True)
    L26.pop("_fail_counts", None)
    n = LL.append_journal([r for r in recs if r["day"] >= "2026"], LL.JOURNAL_PATH)
    print("journal: appended", n, "->", LL.JOURNAL_PATH)
    mode = mode or rep["mode"]
    L = LL.set_mode(L26, mode, rep["verdict"])
    for d in L["decisions"]:
        d["applied"] = False                       # history replay decisions never sized a real trade
    L["history_replay"] = {"built": rep["built"], "verdict": rep["verdict"], "mode": rep["mode"], "resized": rep["resized"],
                           "changes_2026": rep["changes_2026"], "reviews_2026": rep["reviews_2026"],
                           "changes_2021_25": rep["changes_2021_25"], "reviews_2021_25": rep["reviews_2021_25"],
                           **{f"{w}_{s}": {k: rep[w][s].get(k) for k in ("n", "tpw", "pf", "net", "per_month", "dd", "p10", "f10",
                                                                          "p20", "f20", "pass_rate", "funded_net")}
                              for w in ("base", "learned") for s in SP},
                           "file": "research/lit/learn_replay.json", "run": "lit_learn_replay",
                           "writeup": "research/writeups/lit-learning-loop.md"}
    LL.save_learning(L, LL.LEARNING_PATH)
    print("learning ->", LL.LEARNING_PATH, "mode", mode)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        out, recs, L26 = run(save="--nosave" not in sys.argv)
        if "--seed" in sys.argv:
            seed(recs=recs, L26=L26)
    elif cmd == "seed":
        seed()
