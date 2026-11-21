"""FLEET 90 DAYS (day-fleet 2026-11-21; the owner: "find big stuff", the lead: "the biggest lever may be SCALE"). PAPER RESEARCH
ONLY: reads stored trades, writes research/lab/fleet_90day.json. Never buys, trades or edits a live file. Write-up:
research/writeups/fleet-90day-2026-11-21.md.

Built on tools/money/fleet_months.py (the whole fleet on one Monte Carlo, today's seats, real fills = ATLAS 10 ticks a side),
with the owner's 2026-11-20 Decide answers applied to the base:
  A25  ATLAS funded 25K at 40% of the room + 1 micro after 2 ATLAS losses in a row (atlas-funded-room-40 YES, streak YES)
  Z50  Zlarior 50K: LIT alone in the eval, LIT + ATLAS $500 once funded (atlas-on-50k-funded DONE)
  N25  Zlarior 25K #2: LIT alone (zlarior-funded25 NO)      R25 Rapid EOD 25K: LIT + ATLAS $250 (atlas-on-rapid YES)
  R2   5th funded slot = Rapid EOD 50K ($165) bought when money_book.next_buy says yes on BANKED kept payout money.
MFFU's caps (research/lit/mffu_rules.json multi_account, help center re-checked 2026-11-21): 5 sim-funded at 25K/50K, Builder
50K 1, Builder 25K 2, Rapid EOD 50K 3, 10 evals; copy trading across own accounts allowed; hedging across own accounts banned.

Purchase plans compared on the SAME paths (one change each):
  base         as above
  r2-now       buy the Rapid EOD 50K on Mon Nov 23 from your pocket ($165) instead of waiting for payouts
  refill-r50   when a Builder 25K dies (ATLAS's funded 25K lost, or the 25K #2 eval fails), buy a Rapid EOD 50K ($165)
               in its slot instead of a new $63 Builder 25K (at most 3 Rapid EOD 50K in all, MFFU's cap)
  both         r2-now + refill-r50
  par50        a 2nd Builder 50K eval now ($91.80) next to Zlarior's (parallel evals allowed; only one 50K is funded)
  all3         r2-now + refill-r50 + par50
Also: the first live move (a Builder account's 5th payout -> MFFU moves it live and the OTHER sim-funded accounts go dormant,
mffu_rules.json owner_questions_2026_11_20), and the next 3 purchases (which plan, when) from the paths.

    python -X utf8 tools/money/fleet_90day.py            # n = 1000 a market (~10 min on 4 cores)
    python -X utf8 tools/money/fleet_90day.py --n 60     # quick
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fleet_months as FM  # noqa: E402

MP, PD, MB, np = FM.MP, FM.PD, FM.MB, FM.np
ROOT = FM.ROOT
OUT = os.path.join(ROOT, "research", "lab", "fleet_90day.json")
TAX = 0.30                      # the owner's pot rule (STATE: 30% of every payout); day-taxes: 40% if he has a day job
                                # (set on fleet_months only inside job(): importing this module never changes fleet_months)
SPANS = FM.SPANS
WINDOW = ("2026-12", "2027-01", "2027-02")
PLAN = {"Z50": "builder50k", "Z50b": "builder50k", "N25": "builder25k", "A25": "builder25k", "R25": "rapideod25",
        "R2": "rapideod50"}
BUILDER = ("Z50", "N25", "A25")


# ================================================================================================ seats
def a25():
    s = FM.a25(pct=0.4, streak=True)
    return s


def z50(parallel=False):
    return FM.z50(atlas=True, parallel=parallel)


class Swap:
    """A Builder 25K seat whose FIRST death (the seat buys a new eval) is replaced by a Rapid EOD 50K in that slot."""

    def __init__(self, inner, allow):
        self.inner, self.allow, self.r = inner, allow, None
        self.buys = []

    def step(self, k, si):
        if self.r is None:
            o, c = self.inner.step(k, si)
            if c > 0 and k > 0 and self.allow():
                self.r = MP.RSeat(MP.r50_spec(), join=0)
                self.swapped_at = k
                return o, 0.0                     # the $63 re-buy is NOT made: the slot goes to a Rapid EOD 50K
            if c > 0:
                self.buys.append((k, "builder25k"))
            return o, c
        o, c = self.r.step(k, si)
        if c > 0:
            self.buys.append((k, "rapideod50"))
        return o, c

    def funded(self):
        return self.r.funded() if self.r is not None else self.inner.funded()

    @property
    def lost(self):
        return float(getattr(self.inner, "lost", 0) or 0) + float(self.r.lost if self.r is not None else 0)


BASE = {"Z50": z50, "N25": lambda: PD.n25_seat(), "A25": a25, "R25": lambda: FM.r25()}


# ================================================================================================ one fleet run
def run(P, cal, plan="base"):
    n, L = len(P), len(cal)
    par = plan in ("par50", "all3")
    keys = ["Z50", "N25", "A25", "R25", "R2"] + (["Z50b"] if par else [])
    own = {k: np.zeros((n, L)) for k in keys}
    fee = {k: np.zeros((n, L)) for k in keys}
    lost = {k: np.zeros(n) for k in keys}
    r2k = np.full(n, -1)
    buys = []                                   # per path: [(k, plan)]
    swap = plan in ("refill-r50", "both", "all3")
    r2now = plan in ("r2-now", "both", "all3")
    for p, seq in enumerate(P):
        n_r50 = [0]

        def allow():
            if n_r50[0] >= 3:
                return False
            n_r50[0] += 1
            return True

        A = {"Z50": z50(parallel=par), "N25": PD.n25_seat(), "A25": a25(), "R25": FM.r25()}
        if swap:
            A["N25"], A["A25"] = Swap(A["N25"], allow), Swap(A["A25"], allow)
        R2s, pool, pb = None, 0.0, []
        if r2now:
            R2s, r2k[p] = MP.r2_seat(), 1               # bought this weekend, first session Mon Nov 23 (k = 1)
            n_r50[0] += 1
        for k, si in enumerate(seq[:L]):
            for nm, a in A.items():
                o, c = a.step(k, si)
                own[nm][p, k], fee[nm][p, k] = o, c
                if c > 0 and not (nm == "R25" and k == 0) and not isinstance(a, Swap):
                    pb.append((k, PLAN[nm]))
                pool -= c if not (nm == "R25" and k == 0) else 0.0
            if R2s is not None and k >= r2k[p]:
                o, c = R2s.step(k, si)
                own["R2"][p, k], fee["R2"][p, k] = o, c
                if c > 0 and not (r2now and k == r2k[p]):
                    pb.append((k, "rapideod50"))
                pool -= c if not (r2now and k == r2k[p]) else 0.0
            if k >= FM.BANK_LAG:
                pool += sum(own[x][p, k - FM.BANK_LAG] for x in own) * (1 - TAX)
            if R2s is None:
                accts = [{"name": nm, "plan": PLAN[nm], "stage": "funded" if A[nm].funded() else "eval"}
                         for nm in ("Z50", "N25", "A25", "R25")]
                if swap:
                    for x in accts:
                        a = A[x["name"]]
                        if isinstance(a, Swap) and a.r is not None:
                            x["plan"] = "rapideod50"
                nb = MB.next_buy(accts, pool)
                if nb.get("buy") == "rapideod50" and k + 1 < L and n_r50[0] < 3:
                    R2s, r2k[p] = MP.r2_seat(), k + 1
                    n_r50[0] += 1
        for nm, a in A.items():
            lost[nm][p] = float(getattr(a, "lost", 0) or 0)
            if isinstance(a, Swap):
                pb += a.buys
        if R2s is not None:
            lost["R2"][p] = float(R2s.lost or 0)
        if r2now:
            pb.append((1, "rapideod50 (now, from pocket)"))
        buys.append(sorted(pb))
    if par:                                      # the parallel eval lives inside Z50's seat (one seat, two evals)
        del own["Z50b"], fee["Z50b"], lost["Z50b"]
    return {"own": own, "fee": fee, "lost": lost, "r2k": r2k, "buys": buys}


# ================================================================================================ stats
def window_rows(R, cal):
    ms = FM.months(cal)
    M = FM.monthly(R, cal, ms, k8=False)
    rows = []
    for m in WINDOW:
        j = ms.index(m)
        c = M["cash"][:, j]
        rows.append({"month": m, "median": FM.q(c, 50), "bad_1_in_10": FM.q(c, 10), "good_1_in_10": FM.q(c, 90),
                     "mean": round(float(c.mean())), "payouts_median": FM.q(M["pay"][:, j], 50),
                     "fees_mean": round(float(M["fees"][:, j].mean()), 2)})
    jj = [ms.index(m) for m in WINDOW]
    tot3 = M["cash"][:, jj].sum(1)
    tot = M["cash"].sum(1)
    return rows, {"dec_feb_median": FM.q(tot3, 50), "dec_feb_bad": FM.q(tot3, 10), "dec_feb_good": FM.q(tot3, 90),
                  "dec_feb_mean": round(float(tot3.mean())), "to_jun_median": FM.q(tot, 50), "to_jun_bad": FM.q(tot, 10),
                  "to_jun_mean": round(float(tot.mean())), "fees_out_of_pocket_dec_feb_mean":
                      round(float(M["fees"][:, [ms.index("2026-11")] + jj].sum(1).mean()), 2)}


def live_move(R, cal):
    """The session of the first Builder account's 5th payout on each path (MFFU then moves it live; the others go dormant)."""
    n = R["r2k"].shape[0]
    first = []
    for p in range(n):
        ks = []
        for nm in BUILDER:
            pk = np.nonzero(R["own"][nm][p] > 0)[0]
            if len(pk) >= 5:
                ks.append(int(pk[4]))
        first.append(min(ks) if ks else 10 ** 6)
    f = np.array(first)
    ix = lambda d: next((i for i, x in enumerate(cal) if x > d), len(cal))   # noqa: E731
    return {"p_by_feb28": round(100.0 * float((f < ix("2027-02-28")).mean()), 1),
            "p_by_mar31": round(100.0 * float((f < ix("2027-03-31")).mean()), 1),
            "p_by_jun30": round(100.0 * float((f < len(cal)).mean()), 1),
            "median": cal[int(np.median(f))] if np.median(f) < len(cal) else "after Jun 30"}


def dormant(R, cal):
    """MFFU (mffu_rules owner_questions_2026_11_20): once one account moves live the OTHER sim-funded accounts go dormant.
    Bound: every payout after the first live-move session is set to $0 (the live account's own money is unknown, also $0)."""
    n = R["r2k"].shape[0]
    D = {"own": {k: v.copy() for k, v in R["own"].items()}, "fee": R["fee"], "r2k": R["r2k"]}
    for p in range(n):
        ks = []
        for nm in BUILDER:
            pk = np.nonzero(R["own"][nm][p] > 0)[0]
            if len(pk) >= 5:
                ks.append(int(pk[4]))
        if ks:
            f = min(ks)
            for nm in D["own"]:
                D["own"][nm][p, f + 1:] = 0.0
    ms = FM.months(cal)
    t = FM.monthly(D, cal, ms, k8=False)["cash"].sum(1)
    return {"to_jun_mean_if_dormant": round(float(t.mean())), "to_jun_median_if_dormant": FM.q(t, 50)}


def next3(R, cal):
    out = []
    for i in range(3):
        c = collections.Counter()
        dates = collections.defaultdict(list)
        for b in R["buys"]:
            if len(b) > i:
                k, pl = b[i]
                c[pl] += 1
                dates[pl].append(k)
        n = len(R["buys"])
        out.append([{"plan": pl, "share": round(100.0 * v / n, 1),
                     "date_med": cal[int(np.median(dates[pl]))]} for pl, v in c.most_common(3)])
    return out


def per_account(R, cal):
    ms = FM.months(cal)
    out = {}
    for nm in R["own"]:
        t = FM.monthly(R, cal, ms, keys=[nm], k8=False)["cash"]
        jj = [ms.index(m) for m in WINDOW]
        out[nm] = {"dec_feb_mean": round(float(t[:, jj].sum(1).mean())), "to_jun_mean": round(float(t.sum(1).mean())),
                   "lost_mean": round(float(R["lost"][nm].mean()), 2)}
    return out


PLANS = ("base", "r2-now", "refill-r50", "both", "par50", "all3")


def job(a):
    span, plan, n = a
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    t0 = time.time()
    FM.TAX = TAX                                 # this worker's fleet_months.monthly() uses the 30% pot
    FM.set_fills("real")
    cal = FM.calendar()
    P = FM.paths(span, n, len(cal))
    R = run(P, cal, plan)
    rows, tot = window_rows(R, cal)
    r2d = [cal[int(k)] for k in R["r2k"] if k >= 0]
    return {"span": span, "plan": plan, "months": rows, "totals": tot, "accounts": per_account(R, cal),
            "live_move": {**live_move(R, cal), **dormant(R, cal)}, "next3": next3(R, cal),
            "r2": {"p": round(100.0 * len(r2d) / n, 1), "date_med": sorted(r2d)[len(r2d) // 2] if r2d else None},
            "lost_all_mean": round(sum(float(v.mean()) for v in R["lost"].values()), 2), "secs": round(time.time() - t0)}


def study(n=1000, workers=4, log=print):
    res = {"v": 1, "date": "2026-11-21", "n": n, "tax": TAX, "markets": FM.MKT, "window": WINDOW, "plans": PLANS,
           "built_by": "tools/money/fleet_90day.py", "seed": FM.SEED, "rows": {}}
    jobs = [(sp, pl, n) for sp in SPANS for pl in PLANS]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(job, jobs):
            res["rows"].setdefault(r["plan"], {})[r["span"]] = r
            t = r["totals"]
            log(f"{r['plan']:10s} {r['span']:4s} {r['secs']}s Dec-Feb med ${t['dec_feb_median']:,} bad ${t['dec_feb_bad']:,} "
                f"good ${t['dec_feb_good']:,} | to Jun mean ${t['to_jun_mean']:,} | live move by Mar31 "
                f"{r['live_move']['p_by_mar31']}% | lost {r['lost_all_mean']}")
    b = res["rows"]["base"]
    res["vs_base"] = {pl: {sp: {"dec_feb_mean": res["rows"][pl][sp]["totals"]["dec_feb_mean"] - b[sp]["totals"]["dec_feb_mean"],
                                "to_jun_mean": res["rows"][pl][sp]["totals"]["to_jun_mean"] - b[sp]["totals"]["to_jun_mean"],
                                "lost": round(res["rows"][pl][sp]["lost_all_mean"] - b[sp]["lost_all_mean"], 2)}
                           for sp in SPANS} for pl in PLANS if pl != "base"}
    return res


# ================================================================================================ Decide cards
DECISIONS = os.path.join(ROOT, "tools", "web_public", "business", "decisions.json")
NMONTHS = 8                      # Nov 20 - Jun 30 (the per-month $ = the total change / 8, like fleet_months cards)
CARDS = {
    "buy-rapid50-now": {
        "plan": "r2-now",
        "question": "Buy the 5th funded slot (Rapid EOD 50K, $165 with CLUB) now from your pocket, instead of waiting for "
                    "ATLAS's first payout (about Jan 13)?",
        "why": "MFFU allows 5 funded accounts; you hold 4. The Rapid EOD 50K is the biggest earner in the plan, and every "
               "week it waits is a week it is not passing its eval.",
        "applies": "You buy it (Claude never buys); then ADD_ACCOUNT -> Rapid EOD 50K goes in Rapid slot 2 (multi-Rapid, "
                   "landed on pc, OFF until added + your phrase; Sim check first). $165 is $15 over your $150 a round.",
        "recommend": "yes", "price": 165.0},
    "refill-25k-with-rapid50": {
        "plan": "refill-r50",
        "question": "When a Builder 25K dies (ATLAS's funded 25K lost, or the 25K #2 eval fails), put a Rapid EOD 50K "
                    "($165) in that slot instead of a new $63 Builder 25K?",
        "why": "A Builder 25K slot earns a few hundred a month; a Rapid EOD 50K slot earns several times that. MFFU allows "
               "3 Rapid EOD 50Ks, so the swap fits the caps.",
        "applies": "A buying rule for the night an account dies (money_book.dead_eval would say the Rapid EOD 50K); you buy, "
                   "Claude adds it OFF; at most 3 Rapid EOD 50Ks in all.",
        "recommend": "yes", "price": 165.0},
    "second-50k-eval-now": {
        "plan": "par50",
        "question": "Buy a 2nd Builder 50K eval now ($91.80) next to Zlarior's, running the same LIT signal (only the first "
                    "to pass becomes the funded 50K)?",
        "why": "MFFU's public pages allow parallel evals (10 at once; the funded caps apply on the pass), so you don't need "
               "the written yes. Two tries at the 50K = it is funded sooner.",
        "applies": "You buy it; ADD_ACCOUNT -> Builder 50K eval, LIT alone (same as Zlarior's), added OFF + your phrase. "
                   "If one passes, the other is dropped (MFFU funds one Builder 50K).",
        "recommend": "yes", "price": 91.80},
}


def usd(x):
    return ("+" if x >= 0 else "-") + f"${abs(int(x)):,}"


def card_values(res):
    out = {}
    vb = res["vs_base"]
    for cid, C in CARDS.items():
        v = vb[C["plan"]]
        um = {sp: round(v[sp]["to_jun_mean"] / NMONTHS) for sp in SPANS}
        df = {sp: v[sp]["dec_feb_mean"] for sp in SPANS}
        out[cid] = {
            "usd_month": um["H2"], "impact_usd": um["H2"],
            "usd_month_by": {"jul_oct": um["H2"], "half_edge": um["HALF"], "y2021_25": um["REF"]},
            "impact": (f"After MFFU's cut, fees and the 30% tax pot: {usd(um['H2'])} a month to Jun 30 in a Jul-Oct-like "
                       f"market ({usd(um['HALF'])} if the edge halves, {usd(um['REF'])} 2021-25-like); Dec-Feb in total "
                       f"{usd(df['H2'])} / {usd(df['HALF'])} / {usd(df['REF'])}."),
            "risk": (f"Accounts lost by June: {v['H2']['lost']:+.2f} / {v['HALF']['lost']:+.2f} / {v['REF']['lost']:+.2f} "
                     f"(Jul-Oct / half edge / 2021-25-like)."
                     + (f" In a 2021-25-like market it costs ${-v['REF']['to_jun_mean']:,} by June." if v["REF"]["to_jun_mean"] < 0 else "")),
            "recommend_why": (f"{usd(df['H2'])} Dec-Feb and {usd(v['H2']['to_jun_mean'])} by June in a Jul-Oct-like market "
                              f"for ${C['price']:.2f}; still {usd(df['HALF'])} Dec-Feb if the edge halves; the 2021-25-like "
                              f"market costs ${max(0, -v['REF']['to_jun_mean']):,} by June.")}
    return out


def write_cards(res, path=DECISIONS, today="2026-11-21"):
    d = json.load(open(path, encoding="utf-8"))
    vals = card_values(res)
    have = {c["id"]: c for c in d["items"]}
    for cid, C in CARDS.items():
        base = {"id": cid, "question": C["question"], "why": C["why"], "options": ["yes", "no", "later"], "status": "open",
                "source": "research/writeups/fleet-90day-2026-11-21.md", "applies": C["applies"], "added": today,
                "recommend": C["recommend"]}
        v = {**vals[cid], "valued": f"{today} tools/money/fleet_90day.py (whole fleet, 1,000 paths a market, real fills; "
                                    f"$ after MFFU's split, fees and the 30% tax pot)"}
        if cid in have:
            if have[cid].get("status") == "open":
                have[cid].update(v)
        else:
            d["items"].append({**base, **v})
    d["updated"] = today
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--cards", action="store_true", help="write the 3 purchase cards from the saved result")
    a = ap.parse_args(argv)
    if a.cards:
        print("wrote", os.path.relpath(write_cards(json.load(open(a.out, encoding="utf-8"))), ROOT))
        return 0
    res = study(a.n, a.workers)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print("wrote", os.path.relpath(a.out, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
