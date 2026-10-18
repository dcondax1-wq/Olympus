"""Cloud fast-entry watcher check (tools/lit_watch.py + engine/lit_watch.py) on every 2026 session.

    python -X utf8 -m tests.test_lit_watch            # one process, ~30-40 min
    python -X utf8 -m tests.test_lit_watch --months=2026-03 --spot=5   # smoke test on one month
    python -X utf8 -m tests.test_lit_watch --procs=4 --lag=0           # more processes; a real-time feed

What it replays: the GitHub Actions schedule (runs at :02 and :32 ET, 02:02-16:02; a run's monitor looks ~60 s after its
start; a run that finds a LIT setup armed or forming keeps polling; a run queued behind a watching job starts when it
ends, as the workflow's concurrency group does). Bars are fed as they would arrive: at a poll at time `now` the model
sees the 5m and 1m bars that closed by now - lag (Yahoo NQ=F ~10 min late: --lag=600, the default). Each poll from the
day's first LIT signal on is the real engine/lit_live.run (what the monitor and the watcher run), so the entry it shows
is checked against the backtest trade (tools/lit_final.run on the whole history): entry bar, side, price, stop, target,
micros. Before the first signal nothing can be armed or entered, so the forming check (engine/lit_watch.brewing on the
whole-history Market, spot-checked against the live window's Market) decides alone.

Policies (same bars, same schedule): "now" = the half-hourly runs only (before this change), "armed" = watch armed
setups only, "watch" = armed + forming setups with the workflow's budgets (20 min a day forming, 650 min a month).
Reports per policy the delay from the backtest entry to the first poll that shows it (+ the lag), and the Actions
minutes a month it adds (a plain run bills 1 minute; a watching run 1 + its watch time, rounded up per job).
Results -> research/lit/watch_check.json.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from engine import lit, lit_live, lit_watch  # noqa: E402
from engine.data import from_frame, load, load_ltf  # noqa: E402
from tests.test_lit_live import at, day_close, key, ref_key  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "lit", "watch_check.json")
LIVE = os.path.join(ROOT, "live_model.json")
JOB_S = 58             # a plain monitor job today (checkout, install, monitor, publish): bills 1 minute
LOOK_S = 60            # the monitor's poll, after the job's start
WATCH_EVERY = 60       # the replay polls every 60 s (the workflow every 30 s: real delays are up to 30 s shorter)
CAP_S = 55 * 60
FORM_BUDGET_S = 20 * 60
MONTH_BUDGET_S = 650 * 60
G = {}


def _arg(name, default):
    return next((type(default)(a.split("=", 1)[1]) for a in sys.argv if a.startswith(f"--{name}=")), default)


def setup():
    P = {**lit.DEFAULTS, **json.load(open(LIVE, encoding="utf-8"))["lit"]}
    from tools import lit_final as F
    REF = [t for t in F.run(P) if t["day"] >= "2026-01-01"]
    sess = [d for d in F.SESS if d >= "2026-01-01"]
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df5 = df5[df5["time"] >= day_close(sess[0]) - 120 * 86400].reset_index(drop=True)
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
    clean = lit_live._clean5(df5)
    M = lit.Market(bars=from_frame("NQ", "5m", clean), extra_boxes=P.get("extra_boxes") or [])
    s26 = int(np.searchsorted(M.t, at(sess[0], 0, 0)))
    brew = {}
    for j in range(s26, M.n):
        b = lit_watch.brewing(M, P, j)
        if b:
            brew[int(M.t[j]) + 300] = b                 # known once bar j has closed
    # every LIT signal of 2026 with its status (the executor on the whole history, as the backtest)
    C = lit.candidates(M, ref=P["ref"])
    R = lit.run_live(M, C, P, B1=lit.bars_1m(M), B5=lit.bars_5m(M))
    sigs = collections.defaultdict(list)
    for s in R["signals"]:
        if s["day"] >= "2026-01-01":
            sigs[s["day"]].append(s)
    G.update(P=P, REF={t["day"]: t for t in REF}, sess=sess, df5=df5, T5=df5["time"].values, b1=b1, M=M, brew=brew, sigs=sigs,
             n_ref=len(REF))


def poll(now):
    """engine/lit_live.run on the bars closed by `now` (5m + 1m), as the cloud monitor / watcher calls it (no early mode)."""
    df5, T5, b1 = G["df5"], G["T5"], G["b1"]
    cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
    cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
    return lit_live.run(cut5, G["P"], one_min=cut1, now=now)


def brew_at(v):
    return G["brew"].get(v - v % 300)


def crons(d):
    return [at(d, h, m) for h in range(2, 17) for m in (2, 32) if 120 <= h * 60 + m <= 985]


def sim_day(d, policy, lag, memo, month_used):
    """One session under one policy. Returns (detection dict or None, jobs [(start, watch_s)], forming_s, checks)."""
    tr = G["REF"].get(d)
    # the trade's own signal (the setup that fills): from it on every poll is the real engine; earlier no-fill setups of the day
    # count as armed for their 30-min limit window (cost only: nothing can be entered from them)
    own = [s["t"] for s in G["sigs"].get(d, []) if s["status"] == "filled"]
    first_sig = own[-1] if own else None
    arm_iv = [(s["t"], s["t"] + G["P"]["wait"] * 300) for s in G["sigs"].get(d, []) if s["status"] != "filled"]
    det, jobs, form_s, bad = None, [], 0, []

    def state_at(now):
        v = now - lag
        if tr is not None and first_sig is not None and v >= first_sig:
            if v not in memo:
                memo[v] = poll(v)
            return memo[v], v
        return None, v

    def look(now):
        """(alive, why) at a poll + detection bookkeeping."""
        nonlocal det
        if det is not None:                  # the day's entry is in: LIT takes one trade a day, later runs only cost
            return False, "done for today"
        res, v = state_at(now)
        b = brew_at(v)
        if res is None:                      # nothing placed yet today (or a day without a trade): table + signal windows
            if any(a <= v < z for a, z in arm_iv):
                return True, "limit armed"
            return bool(b), "setup forming" if b else "nothing armed"
        st = res["state"]
        pos = st.get("position")
        fin = [t for t in res["trades"] if t["day"] == d]
        if (pos or fin) and det is None:
            k = (pos["entry_t"], pos["dir"], round(pos["entry"], 2), round(pos["stop0"], 2), round(pos["target"], 2), pos["qty"]) \
                if pos else key(fin[0])
            det = {"now": now, "v": v, "shown": "position" if pos else "finished", "same": k == ref_key(tr)}
            if k != ref_key(tr):
                bad.append({"day": d, "now": now, "got": k, "want": ref_key(tr)})
        return lit_watch.alive(res, b)

    free_at, cl, i = 0, crons(d), 0
    while i < len(cl):
        start = max(cl[i], free_at)
        while i + 1 < len(cl) and cl[i + 1] <= start:      # one run waits in the concurrency queue; older ones are dropped
            i += 1
        ok, why = look(start + LOOK_S)
        w = 0
        if policy != "now" and det is None:
            while ok and w < CAP_S:
                if why == "setup forming":
                    if policy == "armed" or form_s >= FORM_BUDGET_S or month_used[0] >= MONTH_BUDGET_S:
                        break
                    form_s += WATCH_EVERY
                w += WATCH_EVERY
                ok, why = look(start + LOOK_S + 30 + w)
                if det is not None:
                    break
        month_used[0] += w
        jobs.append((start, w))
        free_at = start + JOB_S + (w + 30 if w else 0)
        i += 1
    return det, jobs, form_s, bad


def run_chunk(args):
    days, lag = args
    memo = {}
    out = {}
    for pol in ("now", "armed", "watch"):
        month_used = {}
        for d in days:
            mu = month_used.setdefault(d[:7], [0])
            det, jobs, form_s, bad = sim_day(d, pol, lag, memo, mu)
            out[(pol, d)] = {"det": det, "jobs": jobs, "form_s": form_s, "bad": bad}
    return out, len(memo)


def brew_spot_check(n=40):
    """brewing() on the live loop's own window Market (lit_watch.market on the bars so far) == the whole-history table."""
    rng = np.random.default_rng(7)
    keys = sorted(G["brew"])
    pick = [keys[int(x)] for x in rng.choice(len(keys), size=min(n, len(keys)), replace=False)]
    df5, T5 = G["df5"], G["T5"]
    same, diff = 0, []
    for cl in pick:
        cut = df5.iloc[:int(np.searchsorted(T5 + 300, cl, side="right"))]
        live = lit_watch.brewing(lit_watch.market(cut, G["P"]), G["P"])
        a = sorted((b["dir"], b["ext"], b["level"], b["stop"]) for b in live)
        z = sorted((b["dir"], b["ext"], b["level"], b["stop"]) for b in G["brew"][cl])
        if a == z:
            same += 1
        else:
            diff.append({"t": cl, "live": a, "table": z})
    return {"checked": len(pick), "same": same, "diff": diff[:10]}


def main():
    t0 = time.time()
    lag = _arg("lag", 600)
    procs = _arg("procs", 1)
    setup()
    sess, REF = G["sess"], G["REF"]
    print(f"setup: {G['n_ref']} backtest trades, {len(sess)} sessions, forming bars {len(G['brew'])}, "
          f"{sum(len(v) for v in G['sigs'].values())} signals ({time.time() - t0:.0f}s)", flush=True)
    spot = brew_spot_check(_arg("spot", 40))
    print(f"forming check, live window vs whole history: {spot['same']}/{spot['checked']} identical", flush=True)
    months = collections.defaultdict(list)
    only = _arg("months", "")
    for d in sess:
        if not only or d[:7] in only.split(","):
            months[d[:7]].append(d)
    sess = [d for v in months.values() for d in v]
    only = _arg("only", "")
    if only:                                              # --only=2026-01 (a quick run on one month)
        months = {m: v for m, v in months.items() if m.startswith(only)}
        sess = [d for v in months.values() for d in v]
        REF = {d: t for d, t in REF.items() if d in set(sess)}
        G["n_ref"] = len(REF)
    chunks = [(v, lag) for v in months.values()]          # one month per task (the month budget is per month)
    res, polls = {}, 0
    if procs > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(procs) as pool:
            for r, n in pool.imap_unordered(run_chunk, chunks):
                res.update(r); polls += n
                print(f"  ... {len(res) // 3}/{len(sess)} sessions, {time.time() - t0:.0f}s", flush=True)
    else:
        for c in chunks:
            r, n = run_chunk(c)
            res.update(r); polls += n
    out = {"lag_s": lag, "sessions": len(sess), "backtest_trades": G["n_ref"], "real_polls": polls, "forming_spot_check": spot,
           "assumptions": {"job_s": JOB_S, "look_s": LOOK_S, "watch_every_s": WATCH_EVERY, "cap_min": CAP_S / 60,
                           "forming_budget_min_day": FORM_BUDGET_S / 60, "month_budget_min": MONTH_BUDGET_S / 60,
                           "crons": ":02 and :32 ET, 02:02-16:02 (GitHub may start a run several minutes late or skip it)"},
           "policies": {}}
    n_mo = len(sess) / 21.0
    ok = True
    for pol in ("now", "armed", "watch"):
        dl, shown_same, missing, bad, extra_min, watch_min, form_min = [], 0, [], [], 0, 0, 0
        for d in sess:
            r = res[(pol, d)]
            bad += r["bad"]
            extra_min += sum(math.ceil((JOB_S + (w + 30 if w else 0)) / 60) - math.ceil(JOB_S / 60) for _, w in r["jobs"])
            watch_min += sum(w for _, w in r["jobs"]) / 60
            form_min += r["form_s"] / 60
            t = REF.get(d)
            if t is None:
                continue
            if r["det"] is None:
                missing.append(d)
                continue
            shown_same += r["det"]["same"]
            dl.append((r["det"]["now"] - int(t["entry_t"])) / 60.0)
        a = np.array(dl)
        p = {"trades_seen": len(dl), "identical_to_backtest": shown_same, "differences": bad[:20], "n_differences": len(bad),
             "not_seen_same_day": missing,
             "delay_min": {"median": round(float(np.median(a)), 1), "p75": round(float(np.percentile(a, 75)), 1),
                           "p90": round(float(np.percentile(a, 90)), 1), "max": round(float(a.max()), 1),
                           "mean": round(float(a.mean()), 1),
                           "within_2_min_of_feed": int((a <= lag / 60 + 2).sum()), "within_5_min_of_feed": int((a <= lag / 60 + 5).sum()),
                           "within_15": int((a <= 15).sum()), "within_30": int((a <= 30).sum())},
             "delay_after_feed_shows_it_min": {"median": round(float(np.median(a - lag / 60)), 1),
                                               "p90": round(float(np.percentile(a - lag / 60, 90)), 1)},
             "actions_min_month_extra": round(extra_min / n_mo), "watch_min_month": round(watch_min / n_mo),
             "forming_min_month": round(form_min / n_mo)}
        out["policies"][pol] = p
        n_want = sum(1 for d in sess if d in REF)
        ok &= p["n_differences"] == 0 and not missing and shown_same == len(dl) == n_want
        print(f"{pol:6s}: {len(dl)}/{G['n_ref']} entries seen, {shown_same} identical to the backtest, {len(bad)} differences; "
              f"delay from the entry median {p['delay_min']['median']} min (p90 {p['delay_min']['p90']}, max {p['delay_min']['max']}), "
              f"{p['delay_min']['within_2_min_of_feed']} within 2 min of Yahoo showing it; +{p['actions_min_month_extra']} Actions min/month",
              flush=True)
    out["seconds"] = round(time.time() - t0)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    ok &= spot["same"] == spot["checked"]
    print(("OK" if ok else "DIFFERENCES") + f" ({out['seconds']}s, {polls} real polls) -> research/lit/watch_check.json")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
