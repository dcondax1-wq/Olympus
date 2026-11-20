"""FLEET MONTHS (day-fleet 2026-11-20; the owner: "we need to maximize on our money, how much we keep" + "fundeds paying next
month"). PAPER RESEARCH ONLY: reads stored trades, writes research/lab/fleet_months.json and the small phone file
tools/web_public/business/fleet_plan.json. Never trades, arms, buys or edits a live file. Write-up:
research/writeups/fleet-plan-2026-11-20.md.

The whole fleet on ONE Monte Carlo (the same 5-session week-block paths, so a bad week hits every account at once), from
today's board (Fri 2026-11-20) through Wed 2027-06-30:
  Z50  Zlarior Builder 50K eval ($49,193, $3,807 to go, $1,025 room)       } today's seats = tools/money/payday_plan.py
  N25  Zlarior Builder 25K #2 eval ($25,000)                               } (money_plan's live sizing + MFFU rules;
  A25  ATLAS Builder 25K FUNDED ($24,887, $887 room)                       }  a failed eval / lost funded account is
  R25  Rapid EOD 25K eval (bought today, $97.20 sunk)                      }  re-bought at once = money_book.dead_eval)
  R2   the 5th funded slot = a Rapid EOD 50K ($165), bought the session after money_book.next_buy says yes on the KEPT
       payout money (payouts after MFFU's split, minus the tax set-aside, minus every fee paid so far): payouts only.
  K8   Kalshi K8 at $2.50 a bet on the $55 (research/lab/kalshi_clock.json), the stored held-out bets resampled by day;
       stops for good at -$19.25 from its peak (the live kill rule). Kept apart from the NQ total (unproven), then added.
Markets: H2 = 2026 Jul-Oct-like (the fair row), HALF = each week block drawn from Jul-Oct or 2021-25 with even odds (about
half that edge), REF = 2021-25-like (NQ bots made about $0). K8 maps to as-tested / half the edge / no edge.
Fills: "real" = the repo's trade lists with ATLAS at 10 ticks a side (its measured real fills, atlas-risk-real-fills),
LIT as stored (1 + 1 tick); "stress" = LIT also at 10 ticks a side.
Cash to the owner in a month = payouts landing in the bank that month (3 sessions after the request) x (1 - TAX) - fees
paid that month (+ K8). TAX = 0.35, a Maryland-inclusive PLACEHOLDER until day-taxes publishes the exact rate.

    python -X utf8 tools/money/fleet_months.py              # n = 600 a market (~25 min on 4 cores)
    python -X utf8 tools/money/fleet_months.py --n 60       # quick
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import payday_plan as PD  # noqa: E402
import money_plan as MP  # noqa: E402
import money_book as MB  # noqa: E402

BL, U, np, SA = MP.BL, MP.U, MP.np, MP.SA
RL, R25, RLL = MP.RL, MP.R25, MP.RLL
ROOT = MP.ROOT
OUT = os.path.join(ROOT, "research", "lab", "fleet_months.json")
PHONE = os.path.join(ROOT, "tools", "web_public", "business", "fleet_plan.json")
TODAY = START = "2026-11-20"
END = "2027-06-30"
TAX = 0.35                       # placeholder: day-taxes (2026-11-20) says 30% with no day job, 40% with one; owner to say
BANK_LAG = 3                     # sessions from the payout request to the bank
SEED = 2611
SPANS = ("H2", "HALF", "REF")
MKT = {"H2": "Jul-Oct 2026-like", "HALF": "half that edge", "REF": "2021-25-like"}
K8_LEVEL = {"H2": "as_tested", "HALF": "half_edge", "REF": "no_edge"}
PLAN = {"Z50": "builder50k", "N25": "builder25k", "A25": "builder25k", "R25": "rapideod25", "R2": "rapideod50"}
NAMES = {"Z50": "Zlarior 50K", "N25": "Zlarior 25K #2", "A25": "ATLAS funded 25K", "R25": "Rapid EOD 25K",
         "R2": "Rapid EOD 50K (5th slot, from payouts)", "Z50b": "2nd Builder 50K (if MFFU says yes)"}
TICK = 0.25


# ================================================================================================ calendar + months
def calendar():
    import payout_plan as PP
    c = [d for d in PP.calendar(220, START) if d not in PD.CLOSED and d <= END]
    return c


def months(cal):
    ms = sorted({d[:7] for d in cal})
    return ms


# ================================================================================================ fills
def set_fills(kind):
    """'real': ATLAS at 10 ticks a side (LIT as stored). 'stress': LIT at 10 ticks a side too. Clears every trade cache."""
    from tools import atlas_fills as AF
    T = AF.to_T([AF.priced(u, 10, 10) for u in AF.units()])
    AT = [{"day": t["day"], "risk": float(t["risk"]), "tgt": t.get("tgt"), "pts": float(t["pts"]), "w1": float(t["w1"]),
           "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]), "strat": "ATLAS", "src": t["src"]}
          for t in T]
    SA._atlas = lambda: AT
    SA._blitz = lambda: []
    SA._D.clear()
    RL._MB.clear()
    MP._BY.clear()
    if kind == "stress":
        D = SA.data()
        for ts in D["LIT"]:
            for i, t in enumerate(ts):
                ex = 0.0 if str(t.get("exit", "")).upper() == "TARGET" else 9 * TICK
                pts = float(t["pts"]) - 9 * TICK - ex
                ts[i] = {**t, "pts": pts, "w1": min(0.0, float(t["w1"]) - 9 * TICK, pts)}
    return len(AT)


# ================================================================================================ paths
def paths(span, n, length):
    S = SA.data()["S"]
    if span != "HALF":
        return U.mc_paths(S, span, n, length=length, seed=SEED)
    a2, z2 = U.span_ix(S, "H2")
    ar, zr = U.span_ix(S, "REF")
    rng = np.random.default_rng(SEED)
    P = []
    for _ in range(n):
        s = []
        while len(s) < length:
            a, z = (a2, z2) if rng.random() < 0.5 else (ar, zr)
            b = int(rng.integers(a, z - U.BLOCK + 1))
            s.extend(range(b, b + U.BLOCK))
        P.append(s[:length])
    return P


# ================================================================================================ the seats (today's)
class GFS(BL.GF):
    """builder_levers.GF + the atlas-funded-streak-1micro rule (tools/atlas_edge E3): after `streak` losing ATLAS trades in a
    row, ATLAS trades 1 micro until its next winner. The streak counts trades taken before the decision (no look-ahead)."""

    streak_n = 2

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.streak = 0

    def qty(self, t, st):
        q = super().qty(t, st)
        if t.get("strat") != "ATLAS" or q <= 0:
            return q
        if self.streak >= self.streak_n and q > 1:
            q = 1
        self.streak = self.streak + 1 if t["pts"] * U.PV * q - U.COMM * q < 0 else 0
        return q


def a25(ask=None, pct=None, lit=False, streak=False):
    """payday_plan.a25_seat (today's ATLAS funded 25K) with the option of LIT next to ATLAS (the zlarior-funded25 card)
    or the 2-loss 1-micro rule (atlas-funded-streak-1micro)."""
    if not lit and not streak:
        return PD.a25_seat(ask=ask, pct=pct)
    B = MP.by()
    z = {"LIT": ("fq", None), "ATLAS": ("stack", 250.0, 0.3)} if lit else {"ATLAS": ("fq", None)}
    G = GFS if streak else BL.GF
    cfg = dict(U.UP25)
    if pct:
        cfg["pct"] = pct
    s = BL.Seat(lambda _=None: BL.GEv(BL.E25, BL.Zatlas25(), stuck=200.0), lambda: G("builder25k", cfg, z, ask=ask),
                MP.P25, [])
    f = G("builder25k", cfg, z, ask=ask)
    f.bal = f.trade_pnl = MP.A25_PNL
    f.cyc = [MP.A25_PNL]
    f.first_trade, f.elig_from = "2027-01-01", U.cal(0)
    s.evals, s.f, s.wait = [], f, 0
    return MP.BSeat(s, B["A"], B["S"] if lit else B["A"])


def z50(atlas=False, parallel=False):
    """payday_plan.z50_seat from today's hole; atlas = LIT + ATLAS $500 once funded (the advice 'after the pass');
    parallel = a 2nd fresh Builder 50K eval bought today (what a written MFFU yes unlocks, $91.80 now)."""
    B = MP.by()
    fz = BL.F50_LA if atlas else BL.F50_LIT
    ev0 = [BL.GEv(BL.E50, BL.Zlit50(), start=PD.ZL)] + ([BL.GEv(BL.E50, BL.Zlit50())] if parallel else [])
    s = BL.Seat(lambda _=None: BL.GEv(BL.E50, BL.Zlit50()), lambda: BL.GF("builder50k", U.UP50, fz), MP.P50, ev0,
                cost0=MP.P50 if parallel else 0.0)
    return MP.BSeat(s, B["L"], B["LA"] if atlas else B["L"])


def r25(atlas=True, keep=500.0, lane="skip"):
    sp = MP.r25_spec(pol=("cushion", keep), atlas=atlas, lane=lane)
    return MP.RSeat(sp, join=0)


BASE = {"Z50": lambda: z50(), "N25": lambda: PD.n25_seat(), "A25": lambda: a25(), "R25": lambda: r25()}
# open Decide cards -> the YES side (one change); 'no_side' = the stored default is already YES (the card asks to keep it)
CARDS = {
    "zlarior-atlas-50k": ("ATLAS on Zlarior's 50K once funded (LIT + ATLAS $500)", {"Z50": lambda: z50(atlas=True)}),
    "atlas-on-rapid": ("Rapid: ATLAS next to Zlarior (built ON; NO = LIT alone)", {"R25": lambda: r25(atlas=False)}),
    "rapid25-lit-bank": ("Rapid 25K: LIT 1 micro banked at the day's room", {"R25": lambda: r25(lane="bank1")}),
    "zlarior-funded25": ("ATLAS's funded 25K: LIT trades it too", {"A25": lambda: a25(lit=True)}),
    "atlas-funded-room-40": ("ATLAS's funded 25K at 40% of the room", {"A25": lambda: a25(pct=0.4)}),
    "atlas-funded-streak-1micro": ("ATLAS's funded 25K: 1 micro after 2 losses in a row", {"A25": lambda: a25(streak=True)}),
    "payout-ping-1000": ("Ask at $1,000 instead of $750 (both 25Ks)", {"A25": lambda: a25(ask=1000.0),
                                                                        "N25": lambda: PD.n25_seat(ask=1000.0)}),
    "keep-1000-rapid": ("Keep $1,000 in each Rapid at payouts", {"R25": lambda: r25(keep=1000.0)}),
    "ask-mffu-parallel": ("A written MFFU yes -> a 2nd Builder 50K eval now", {"Z50": lambda: z50(parallel=True)}),
}
NO_SIDE = {"atlas-on-rapid"}              # the variant is the NO answer: YES effect = base - variant
ZERO_CARDS = {"cloud-alerts": "no $ change (it protects against a silent PC)",
              "drop-lucid-account4": "no $ change (a page fix)"}


# ================================================================================================ the fleet run
def _k8_days():
    import kalshi_bankroll as KB
    test = KB.load(period="test")
    st = KB.stats(test)
    w, be = st["win_rate"], st["break_even_win_rate"]
    flips = {"as_tested": 0.0, "half_edge": 1 - ((w + be) / 2) / w, "no_edge": 1 - be / w}
    return list(test.values()), flips, st["avg_loss_per_$1"]


def k8_path(rng, pool, flip, al, nd, stake, kill):
    """One path of K8 daily $ (nd days): flat stake, a day's bets move together, OFF for good at -kill from the peak."""
    out = np.zeros(nd)
    cash = peak = 0.0
    for d in range(nd):
        day = 0.0
        for won, r in pool[rng.randrange(len(pool))]:
            if won and flip and rng.random() < flip:
                won, r = 0, -al
            day += stake * r
        cash += day
        out[d] = day
        peak = max(peak, cash)
        if peak - cash >= kill:
            break
    return out


def run(P, cal, makers, base=None, r2=True, kalshi=None):
    """All accounts on paths P. base = a previous result: seats not in makers are copied from it (same paths), R2 re-run.
    -> own / fee per seat (n x L), r2 buy session, K8 per day."""
    n, L = len(P), len(cal)
    keys = sorted(set(makers) | (set(base["own"]) - {"R2"} if base else set()))
    own = {k: np.zeros((n, L)) for k in keys + ["R2"]}
    fee = {k: np.zeros((n, L)) for k in keys + ["R2"]}
    lost = {k: np.zeros(n) for k in keys + ["R2"]}
    fund = {k: np.zeros((n, L), dtype=bool) for k in keys}
    r2k = np.full(n, -1)
    for p, seq in enumerate(P):
        A = {k: m() for k, m in makers.items()}
        R2s, pool = None, 0.0
        for k, si in enumerate(seq[:L]):
            for nm in keys:
                if nm in A:
                    o, c = A[nm].step(k, si)
                    own[nm][p, k], fee[nm][p, k], fund[nm][p, k] = o, c, A[nm].funded()
                else:
                    o, c = base["own"][nm][p, k], base["fee"][nm][p, k]
                    own[nm][p, k], fee[nm][p, k], fund[nm][p, k] = o, c, base["fund"][nm][p, k]
                pool -= c if not (nm == "R25" and k == 0) else 0.0
            if R2s is not None:
                o, c = R2s.step(k, si)
                own["R2"][p, k], fee["R2"][p, k] = o, c
                pool -= c
            if k >= BANK_LAG:                                # a payout is spendable once it is in the bank
                pool += sum(own[nm][p, k - BANK_LAG] for nm in own) * (1 - TAX)
            if R2s is None and r2:
                accts = [{"name": nm, "plan": PLAN[nm], "stage": "funded" if fund[nm][p, k] else "eval"}
                         for nm in ("Z50", "N25", "A25", "R25")]
                nb = MB.next_buy(accts, pool)
                if nb.get("buy") == "rapideod50" and k + 1 < L:
                    R2s, r2k[p] = MP.r2_seat(), k + 1      # bought after today's close: trades from the next session
        for nm, a in A.items():
            lost[nm][p] = float(getattr(a, "lost", 0) or 0)
        if R2s is not None:
            lost["R2"][p] = float(R2s.lost or 0)
    out = {"own": own, "fee": fee, "fund": fund, "lost": lost, "r2k": r2k}
    if base is not None:
        for nm in keys:
            if nm not in makers:
                out["lost"][nm] = base["lost"][nm]
        out["k8"] = base.get("k8")
    elif kalshi is not None:
        out["k8"] = kalshi
    return out


def k8_run(n, L, level):
    pool, flips, al = _k8_days()
    kc = json.load(open(os.path.join(ROOT, "research", "lab", "kalshi_clock.json"), encoding="utf-8"))
    rng = random.Random(SEED)
    return np.array([k8_path(rng, pool, flips[level], al, L, float(kc["stake_usd"]), float(kc["kill_drawdown_usd"]))
                     for _ in range(n)]), {"stake": kc["stake_usd"], "bankroll": kc["bankroll_usd"],
                                           "kill_from_peak": kc["kill_drawdown_usd"], "level": level}


# ================================================================================================ money by month
def monthly(R, cal, ms, keys=None, k8=True):
    """-> per path x month: cash to the owner after the tax set-aside (payouts land BANK_LAG sessions later), payouts before
    tax, fees. Payouts that would land after END are dropped (they are July money)."""
    n, L = R["r2k"].shape[0], len(cal)
    mi = np.array([ms.index(d[:7]) for d in cal])
    keys = keys or list(R["own"])
    pay = np.zeros((n, len(ms)))
    fees = np.zeros((n, len(ms)))
    for nm in keys:
        o, f = R["own"][nm], R["fee"][nm].copy()
        if nm == "R25":
            f[:, 0] = 0.0                                   # today's $97.20 is already paid (sunk)
        for k in range(L):
            kb = k + BANK_LAG
            if kb < L:
                pay[:, mi[kb]] += o[:, k]
            fees[:, mi[k]] += f[:, k]
    kal = np.zeros((n, len(ms)))
    if k8 and R.get("k8") is not None:
        for k in range(L):
            kal[:, mi[k]] += R["k8"][:, k]
    cash = pay * (1 - TAX) - fees + kal * (1 - TAX)
    return {"cash": cash, "pay": pay, "fees": fees, "k8": kal}


def q(a, p):
    return round(float(np.percentile(a, p)))


def summary(R, cal, ms):
    M = monthly(R, cal, ms)
    rows = []
    for j, m in enumerate(ms):
        rows.append({"month": m, "median": q(M["cash"][:, j], 50), "bad_1_in_10": q(M["cash"][:, j], 10),
                     "good_1_in_10": q(M["cash"][:, j], 90), "mean": round(float(M["cash"][:, j].mean())),
                     "payouts_before_tax_median": q(M["pay"][:, j], 50), "fees_mean": round(float(M["fees"][:, j].mean()), 2),
                     "k8_mean": round(float(M["k8"][:, j].mean() * (1 - TAX)), 2),
                     "p_any_cash": round(100.0 * float((M["pay"][:, j] > 0).mean()), 1)})
    tot = M["cash"].sum(1)
    acc = {}
    for nm in R["own"]:
        Mi = monthly(R, cal, ms, keys=[nm], k8=False)
        t = Mi["cash"].sum(1)
        fp = np.array([int(np.argmax(r > 0)) if (r > 0).any() else -1 for r in R["own"][nm]])
        acc[nm] = {"name": NAMES.get(nm, nm), "total_median": q(t, 50), "total_bad": q(t, 10), "total_mean": round(float(t.mean())),
                   "per_month_mean": round(float(t.mean()) / len(ms)),
                   "p_paid": round(100.0 * float((fp >= 0).mean()), 1),
                   "first_pay_med": cal[int(np.median(fp[fp >= 0]))] if (fp >= 0).any() else None,
                   "lost_or_failed_mean": round(float(R["lost"][nm].mean()), 2),
                   "rebuys_mean": round(float((R["fee"][nm][:, 1:] > 0).sum(1).mean()), 2),
                   "fees_mean": round(float(R["fee"][nm][:, (1 if nm == "R25" else 0):].sum(1).mean()), 2)}
    r2 = R["r2k"]
    r2d = [cal[int(k)] for k in r2 if k >= 0]
    buy = {"what": "Rapid EOD 50K", "price": MB.OWNER_PRICE["rapideod50"], "code": "CLUB",
           "p_bought": round(100.0 * float((r2 >= 0).mean()), 1),
           "date_med": sorted(r2d)[len(r2d) // 2] if r2d else None,
           "date_p10": sorted(r2d)[int(0.1 * len(r2d))] if r2d else None,
           "date_p90": sorted(r2d)[int(0.9 * len(r2d))] if r2d else None}
    return {"months": rows, "total_median": q(tot, 50), "total_bad": q(tot, 10), "total_good": q(tot, 90),
            "total_mean": round(float(tot.mean())), "per_month_mean": round(float(tot.mean()) / len(ms)),
            "p_total_below_0": round(100.0 * float((tot < 0).mean()), 1),
            "k8_total_mean": round(float(M["k8"].sum(1).mean() * (1 - TAX))),
            "accounts": acc, "next_buy": buy}


def card_effect(base, var, cal, ms, no_side=False):
    a = monthly(base, cal, ms)["cash"].sum(1)
    b = monthly(var, cal, ms)["cash"].sum(1)
    d = (a - b) if no_side else (b - a)
    nm = len(ms)
    return {"usd_month_mean": round(float(d.mean()) / nm), "usd_month_median_shift":
            round((float(np.median(a if no_side else b)) - float(np.median(b if no_side else a))) / nm),
            "bad_1_in_10_shift": round((float(np.percentile(a if no_side else b, 10)) -
                                        float(np.percentile(b if no_side else a, 10))) / nm),
            "p_better": round(100.0 * float((d > 0).mean()), 1),
            "accounts_lost_change": round(sum(float(var["lost"][k].mean() - base["lost"][k].mean()) for k in var["lost"])
                                          * (-1 if no_side else 1), 2)}


# ================================================================================================ one market (a worker)
def market(job):
    span, fills, n, cards = job
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    t0 = time.time()
    set_fills(fills)
    cal = calendar()
    ms = months(cal)
    P = paths(span, n, len(cal))
    k8, k8meta = k8_run(n, len(cal), K8_LEVEL[span])
    B = run(P, cal, BASE, kalshi=k8)
    out = {"span": span, "fills": fills, "summary": summary(B, cal, ms), "k8": k8meta, "cards": {}}
    if cards:
        for cid, (words, mk) in CARDS.items():
            V = run(P, cal, mk, base=B)
            out["cards"][cid] = {"what": words, **card_effect(B, V, cal, ms, cid in NO_SIDE)}
    out["secs"] = round(time.time() - t0)
    return out


def study(n=600, workers=4, log=print):
    jobs = [(sp, "real", n, True) for sp in SPANS] + [(sp, "stress", n, False) for sp in SPANS]
    cal = calendar()
    res = {"v": 1, "date": TODAY, "start": START, "end": cal[-1], "sessions": len(cal), "n": n, "months": months(cal),
           "markets": MKT, "tax": TAX, "tax_note": "35% set aside = the middle of day-taxes' Maryland pot (30% with no day job, 40% with one) until you say which",
           "bank_lag_sessions": BANK_LAG, "seed": SEED, "names": NAMES, "built_by": "tools/money/fleet_months.py",
           "fills": {"real": "ATLAS 10 ticks a side (its measured fills), LIT as stored (1 + 1 tick)",
                     "stress": "LIT at 10 ticks a side too"},
           "caps": {"funded": MB.FUNDED_CAP, "evals": MB.EVAL_CAP, "per_plan": MB.PLAN_CAP},
           "prices": MB.OWNER_PRICE, "zero_cards": ZERO_CARDS, "rows": {}}
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(market, jobs):
            res["rows"].setdefault(r["fills"], {})[r["span"]] = r
            s = r["summary"]
            log(f"{r['fills']:6s} {r['span']:4s} {r['secs']}s: total median ${s['total_median']:,} bad ${s['total_bad']:,} "
                f"${s['per_month_mean']:,}/mo, R2 {s['next_buy']['p_bought']}% med {s['next_buy']['date_med']}")
    res["secs"] = round(time.time() - t0)
    res["ranked_cards"] = rank_cards(res)
    res["check"] = check_block()
    return res


CHECK_N = 12


def check_block():
    """A tiny re-run the test repeats: the same code on the same trade lists must give these numbers to the dollar."""
    r = market(("H2", "real", CHECK_N, False))["summary"]
    return {"n": CHECK_N, "span": "H2", "fills": "real", "total_median": r["total_median"], "total_mean": r["total_mean"],
            "months_median": [m["median"] for m in r["months"]], "r2_date_med": r["next_buy"]["date_med"]}


def rank_cards(res):
    R = res["rows"]["real"]
    out = []
    for cid in CARDS:
        e = {sp: R[sp]["cards"][cid] for sp in SPANS if cid in R[sp].get("cards", {})}
        if not e:
            continue
        out.append({"id": cid, "what": CARDS[cid][0], "by_market": e,
                    "usd_month": e["H2"]["usd_month_mean"], "usd_month_half": e["HALF"]["usd_month_mean"],
                    "usd_month_ref": e["REF"]["usd_month_mean"]})
    for cid, why in ZERO_CARDS.items():
        out.append({"id": cid, "what": why, "usd_month": 0, "usd_month_half": 0, "usd_month_ref": 0})
    out.sort(key=lambda r: -(abs(r["usd_month"]) + abs(r["usd_month_half"])))
    return out


# ================================================================================================ the phone file
def phone(res):
    """Small and stable: every number is copied from the study result (tests check that)."""
    H = res["rows"]["real"]
    s2, sh, sr = H["H2"]["summary"], H["HALF"]["summary"], H["REF"]["summary"]
    st = res["rows"]["stress"]["H2"]["summary"]
    top = []
    for c in res["ranked_cards"][:3]:
        top.append({"id": c["id"], "what": c["what"], "yes_usd_month": c["usd_month"], "yes_usd_month_half": c["usd_month_half"],
                    "yes_usd_month_ref": c["usd_month_ref"]})
    return {"v": 1, "date": res["date"], "source": "research/lab/fleet_months.json (tools/money/fleet_months.py)",
            "tax": res["tax"], "tax_note": res["tax_note"], "n": res["n"],
            "markets": {"H2": MKT["H2"], "HALF": MKT["HALF"], "REF": MKT["REF"]},
            "months": [{"m": r["month"], "month": r["month"], "median": r["median"], "bad": r["bad_1_in_10"],
                        "median_half": h["median"], "median_ref": f["median"]}
                       for r, h, f in zip(s2["months"], sh["months"], sr["months"])],
            "total": {"median": s2["total_median"], "bad": s2["total_bad"], "median_half": sh["total_median"],
                      "median_ref": sr["total_median"], "median_stress": st["total_median"]},
            "next_buy": {"what": s2["next_buy"]["what"], "price": s2["next_buy"]["price"], "code": s2["next_buy"]["code"],
                         "when_med": s2["next_buy"]["date_med"], "when_p10": s2["next_buy"]["date_p10"],
                         "when_p90": s2["next_buy"]["date_p90"], "chance": s2["next_buy"]["p_bought"],
                         "from": "kept payout money only (after MFFU's cut, the tax set-aside and fees)",
                         "when": s2["next_buy"]["date_med"], "usd": s2["next_buy"]["price"],
                         "why": (f"5th funded slot, the biggest earner (median ${s2['accounts']['R2']['total_median']:,} by June); "
                                 f"8 in 10 runs between {s2['next_buy']['date_p10']} and {s2['next_buy']['date_p90']}, "
                                 f"paid from payouts in the bank")},
            "top_cards": top,
            "top_decide": [{"id": c["id"], "title": c["what"], "usd": c["yes_usd_month"]} for c in top]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--phone-only", action="store_true", help="rebuild fleet_plan.json from the saved result")
    ap.add_argument("--check-only", action="store_true", help="redo the saved result's small check block")
    a = ap.parse_args(argv)
    if a.phone_only or a.check_only:
        res = json.load(open(a.out, encoding="utf-8"))
        if a.check_only:
            res["check"] = check_block()
            with open(a.out, "w", encoding="utf-8") as fh:
                json.dump(res, fh, indent=1, default=float)
    else:
        res = study(a.n, a.workers)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, default=float)
        print("wrote", os.path.relpath(a.out, ROOT))
    if a.out == OUT:
        with open(PHONE, "w", encoding="utf-8") as fh:
            json.dump(phone(res), fh, indent=1)
        print("wrote", os.path.relpath(PHONE, ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
