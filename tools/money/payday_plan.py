"""PAYDAY PLAN (2026-11-20 night-payday; the owner: "We need these fundeds paying next month latest"). PAPER RESEARCH ONLY:
reads stored trades, writes research/lab/payday_plan.json (the Business > Goals page reads it via tools/money/goals_build.py)
and research/lab/payday_levers.json (Lab rows). Never trades, arms or edits a live file. Design fixed BEFORE the first run:
research/lab/payday_design_2026-11-20.md (8 levers, 2 loss cuts, the judge).

What it plays: tools/money/money_plan.py's seats (the live sizing code and MFFU rules as coded there) from TODAY's board
(2026-11-19 21:40 ET), every account on the SAME Monte Carlo paths (5-session week blocks), from Fri 2026-11-20:
  Z50  Zlarior Builder 50K eval  $49,193, $3,807 to pass, $1,025 room, session 25 on Nov 20
  N25  Zlarior Builder 25K #2    $25,000, $1,500 to pass, $1,000 room, session 3 on Nov 20
  A25  ATLAS Builder 25K FUNDED  $24,887, $887 room, the cycle has 1 traded day (-$113), the 48 h wait is over
  R25  Rapid EOD 25K             bought tonight, first session Nov 20 (LIT + ATLAS $250, 30% guard, keep $500)
Thanksgiving Thu Nov 26 = no session (the bot does not trade it); Fri Nov 27 counted as a normal session.
Per account: the first payout's date (median, 80% range p10-p90 over ALL paths), its $ to you (after MFFU's split), the
chance it pays by Dec 31 / Jan 15 / Jan 31, the chance the account is lost before it pays (a re-buy came first).

    python -X utf8 tools/money/payday_plan.py              # n = 1000 a market (~10-20 min; run it through /home/user/heavy.sh)
    python -X utf8 tools/money/payday_plan.py --n 150      # quick
    python -X utf8 tools/money/payday_plan.py --only plan  # the plan only (no levers)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import money_plan as MP  # noqa: E402

BL, U, np, SA = MP.BL, MP.U, MP.np, MP.SA
B25, R25, RLL, F25 = MP.B25, MP.R25, MP.RLL, MP.F25
ROOT = MP.ROOT
OUT = os.path.join(ROOT, "research", "lab", "payday_plan.json")
LAB = os.path.join(ROOT, "research", "lab", "payday_levers.json")
TODAY, START = "2026-11-20", "2026-11-20"
CLOSED = {"2026-11-26"}                         # Thanksgiving: no session for the bot (13:00 halt)
LEN, MO = MP.LEN, MP.MO
SPANS = ("H2", "H1", "REF")
ZL = {"room": 1025.0, "to_go": 3807.0, "session": 24}          # GEv adds 1 before the first step: Nov 20 = session 25
N25_S0 = 2                                                       # Nov 18 + Nov 19 (no trade): Nov 20 = session 3
A25_STATE = None                                                 # None = Nov 20 (money_plan.A25_PNL); --asof sets it
# --asof: the board's numbers on a later day (the public status post, tools/board.fetch_lite). 2026-11-23 (night-payplan): Z50 $49,214,
# $3,786 to pass, $1,046 room, session 26; N25 $25,024, session 4; ATLAS funded +$401 (days -$113, +$514; floor $24,401 = $1,000 room);
# Rapid EOD 25K $25,000, session 2 (no trade yet).
ASOF = {"2026-11-23": {"zl": {"room": 1045.7, "to_go": 3786.1, "session": 25}, "n25_s0": 3,
                       "a25": {"bal": 401.38, "cyc": [-113.0, 514.0], "peak": 401.38}}}
KEYS = ("Z50", "N25", "A25", "R25")
NAMES = {"Z50": "Zlarior 50K (eval)", "N25": "Zlarior 25K #2 (eval)", "A25": "ATLAS 25K (funded)", "R25": "Rapid EOD 25K (eval)"}
SPLIT = {"Z50": 0.8, "N25": 0.8, "A25": 0.8, "R25": 0.9}
TAX = MP.TAX
B25.OPTS.setdefault("room 40% + cap $300", (B25.tw(0.4, 300), None, None))


class GFFirst(BL.GF):
    """night-payfirst 2026-11-23 (owner: "take it sooner, one payout small so we can immediately buy more accounts"): ATLAS asks its
    FIRST payout on the first day MFFU allows one (engine/funded_life first_at_min: >= $250 above the buffer, every rule kept), then
    the normal plan (the full max). The live code's rule, played on the same paths."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._ask0 = float(self.P["ask_above"])

    def _fast_track(self, day):
        self.P["ask_above"] = float(self.P["pay_min"]) if not self.pays else self._ask0
        return super()._fast_track(day)


A25_FIRST_AT_MIN = True          # engine/account_b.ATLAS_FIRST_AT_MIN (owner 2026-11-23)


# ================================================================================================ the seats from TODAY
def z50_seat():
    B = MP.by()
    s = BL.Seat(lambda _=None: BL.GEv(BL.E50, BL.Zlit50()), lambda: BL.GF("builder50k", U.UP50, BL.F50_LIT), MP.P50,
                [BL.GEv(BL.E50, BL.Zlit50(), start=ZL)])
    return MP.BSeat(s, B["L"], B["L"])


def n25_seat(ask=None, opt=None):
    B = MP.by()
    fz = {"LIT": ("fq", None)}
    mk = lambda: B25.Ev25(opt or B25.BASE)       # noqa: E731
    e0 = mk()
    e0.s = N25_S0
    s = BL.Seat(lambda _=None: mk(), lambda: BL.GF("builder25k", U.UP25, fz, ask=ask), MP.P25, [e0])
    return MP.BSeat(s, B["L"], B["L"])


def a25_seat(ask=None, pct=None, need=None, BYa=None):
    B = MP.by()
    BYa = BYa or B["A"]
    z = {"ATLAS": ("fq", None)}
    cfg = dict(U.UP25)
    if pct:
        cfg["pct"] = pct
    if need:
        cfg["need"] = need
    G = GFFirst if A25_FIRST_AT_MIN and ask is None else BL.GF       # a lever's own ask keeps its old meaning
    s = BL.Seat(lambda _=None: BL.GEv(BL.E25, BL.Zatlas25(), stuck=200.0), lambda: G("builder25k", cfg, z, ask=ask),
                MP.P25, [])
    f = G("builder25k", cfg, z, ask=ask)
    if A25_STATE:
        f.bal = f.trade_pnl = A25_STATE["bal"]
        f.cyc = list(A25_STATE["cyc"])
        f.peak = A25_STATE["peak"]
        f.floor = min(max(f.floor, f.peak - float(f.A["mll"])), float(f.A.get("lock", 100.0)))
    else:
        f.bal = f.trade_pnl = MP.A25_PNL
        f.cyc = [MP.A25_PNL]
    f.first_trade, f.elig_from = "2027-01-01", U.cal(0)          # the 48 h first wait ended before Nov 20
    s.evals, s.f, s.wait = [], f, 0
    return MP.BSeat(s, BYa, BYa)


def r25_seat(atlas=None, lane="skip"):
    if lane != "skip":
        sp = RLL.spec(lane)
    else:
        sp = R25.acct("25k", ("cushion", 500.0), atlas=atlas)
    return MP.RSeat(sp, join=0)


BASE = {"Z50": z50_seat, "N25": n25_seat, "A25": a25_seat, "R25": r25_seat}
LEVERS = {   # the design file's 8 (L4 runs on combo_account: combo_now())
    "atlas-funded-room-40": ("L1", "ATLAS funded 25K at 40% of the room a trade (today 60%)", {"A25": lambda: a25_seat(pct=0.4)}),
    "payout-ping-1000": ("L2", "Ask at $1,000 above the buffer instead of $750 (ATLAS 25K, and the 25K #2 once funded)",
                         {"A25": lambda: a25_seat(ask=1000.0), "N25": lambda: n25_seat(ask=1000.0)}),
    "a25-need": ("L3", "ATLAS funded 25K: risk only what reaches the next $1,000 request line (never above today's 60%)",
                 {"A25": lambda: a25_seat(need=1.0)}),
    "n25-cap300": ("L5", "25K #2 eval: 40% of the room (your rule) with a $300 cap a trade",
                   {"N25": lambda: n25_seat(opt="room 40% + cap $300")}),
    "r25-atlas150": ("L6", "Rapid 25K: ATLAS lane $150 a trade (today $250)", {"R25": lambda: r25_seat(atlas=150)}),
    "r25-atlas350": ("L7", "Rapid 25K: ATLAS lane $350 a trade (today $250)", {"R25": lambda: r25_seat(atlas=350)}),
    "rapid25-lit-bank": ("L8", "Rapid 25K: Zlarior 1 micro banked at the day's 30% room when the guard says 0",
                         {"R25": lambda: r25_seat(lane="bank1")}),
}


def calendar():
    import payout_plan as PP
    c = [d for d in PP.calendar(LEN + 10, START) if d not in CLOSED]
    return c[:LEN + 5]


# ================================================================================================ running + stats
def run(paths, makers):
    """Every account in makers on the same paths -> per account own / fee / funded arrays (n x LEN)."""
    n = len(paths)
    R = {k: {"own": np.zeros((n, LEN)), "fee": np.zeros((n, LEN)), "fund": np.zeros((n, LEN), dtype=bool), "lost": np.zeros(n)}
         for k in makers}
    for p, seq in enumerate(paths):
        A = {k: m() for k, m in makers.items()}
        for k, si in enumerate(seq[:LEN]):
            for nm, a in A.items():
                o, c = a.step(k, si)
                R[nm]["own"][p, k], R[nm]["fee"][p, k] = o, c
                R[nm]["fund"][p, k] = a.funded()
        for nm, a in A.items():
            R[nm]["lost"][p] = float(getattr(a, "lost", 0) or 0)
    return R


def _first(m):
    return np.array([int(np.argmax(r)) if r.any() else -1 for r in m])


def _date(cal, k):
    return cal[int(k)] if k is not None and 0 <= k < LEN else None


def acct(r, cal, key):
    own, fee, fund = r["own"], r["fee"].copy(), r["fund"]
    if key == "R25":
        fee[:, 0] = 0.0                              # the purchase tonight (sunk), not a re-buy
    n = own.shape[0]
    fp = _first(own > 0)
    big = np.where(fp >= 0, fp, 10 ** 6)
    q = {p: np.percentile(big, p) for p in (10, 25, 50, 75, 90)}
    amt = np.array([own[i, fp[i]] for i in range(n) if fp[i] >= 0])
    fr = _first(fee > 0)
    lost_first = ((fr >= 0) & ((fp < 0) | (fr < fp)))
    ff = _first(fund)
    by = lambda d: round(100.0 * float(((fp >= 0) & (fp < next(i for i, x in enumerate(cal) if x > d))).mean()), 1)   # noqa: E731
    cash = own - fee
    out = {"name": NAMES[key], "first_pay_p10": _date(cal, q[10] if q[10] < LEN else None),
           "first_pay_p25": _date(cal, q[25] if q[25] < LEN else None),
           "first_pay_med": _date(cal, q[50] if q[50] < LEN else None),
           "first_pay_p75": _date(cal, q[75] if q[75] < LEN else None),
           "first_pay_p90": _date(cal, q[90] if q[90] < LEN else None),
           "first_pay_k_med": float(q[50]) + 1 if q[50] < LEN else None,
           "first_pay_usd": round(float(np.median(amt))) if len(amt) else None,
           "first_pay_usd_p10": round(float(np.percentile(amt, 10))) if len(amt) else None,
           "first_pay_usd_p90": round(float(np.percentile(amt, 90))) if len(amt) else None,
           "p_by_dec31": by("2026-12-31"), "p_by_jan15": by("2027-01-15"), "p_by_jan31": by("2027-01-31"),
           "p_no_pay_6m": round(100.0 * float((fp < 0).mean()), 1),
           "p_lost_before_pay": round(100.0 * float(lost_first.mean()), 1),
           "lost_6m": round(100.0 * float((r["lost"] > 0).mean()), 1),
           "cash_m": round(float(cash.sum(1).mean()) / MO), "paid_6m": round(float(own.sum(1).mean()))}
    if key != "A25":
        fg = ff[ff >= 0]
        out["funded_med"] = _date(cal, int(np.median(fg))) if len(fg) else None
        out["funded_p10"] = _date(cal, int(np.percentile(np.where(ff >= 0, ff, 10 ** 6), 10))) if len(fg) else None
        out["p_funded_by_dec31"] = round(100.0 * float(((ff >= 0) & (ff < next(i for i, x in enumerate(cal) if x > "2026-12-31"))).mean()), 1)
        out["p_eval_fail_first"] = round(100.0 * float(((fr >= 0) & ((ff < 0) | (fr < ff))).mean()), 1)
    return out, fp


def fleet(fps, cal):
    fa = np.min(np.where(np.array(fps) >= 0, np.array(fps), 10 ** 6), axis=0)
    ix = lambda d: next(i for i, x in enumerate(cal) if x > d)   # noqa: E731
    med = np.median(fa)
    return {"first_any_med": _date(cal, med if med < LEN else None),
            "first_any_p10": _date(cal, np.percentile(fa, 10)), "first_any_p90": _date(cal, np.percentile(fa, 90) if np.percentile(fa, 90) < LEN else None),
            "p_any_by_dec31": round(100.0 * float((fa < ix("2026-12-31")).mean()), 1),
            "p_any_by_jan15": round(100.0 * float((fa < ix("2027-01-15")).mean()), 1),
            "p_any_by_jan31": round(100.0 * float((fa < ix("2027-01-31")).mean()), 1),
            "p_two_by_jan31": round(100.0 * float((np.sum(np.array([(f >= 0) & (f < ix("2027-01-31")) for f in fps]), axis=0) >= 2).mean()), 1)}


# ================================================================================================ L4: the 50K combo now vs after
def combo_now(n=600, log=print):
    """combo_account's own Slot from today's hole: Zlarior alone in the eval then Z+A funded (= after the pass) vs ATLAS at
    50% in the eval NOW (a50_eval). Same week-block paths both sides. -> span -> {after, now} stats."""
    import combo_account as CA
    cal = calendar()
    out = {}
    for sp in SPANS:
        paths = CA.week_paths(sp, n, CA.SEED_WEEK)
        res = {}
        for side, vid in (("after", "a_eval_off"), ("now", "a50_eval")):
            r = CA.frow(vid)
            De = CA.combo_days(r["eval"])
            Df = CA.combo_days(r["funded"])
            fps, fails, lost, own6 = [], 0, 0, []
            for seq in paths:
                s = CA.Slot(r)
                s.cost = 0.0                                   # the eval is already paid for
                e = s.e
                e.bal = 3000.0 - ZL["to_go"]
                e.floor = e.bal - ZL["room"]
                e.peak = e.floor + e.mll
                e.s = ZL["session"]
                e.dtr = 10
                fr = None
                for k, si in enumerate(seq):
                    c0 = s.cost
                    s.step(k, De[si], Df[si])
                    if s.cost > c0 and fr is None:
                        fr = k
                fp = (s.first_pay - 1) if s.first_pay else -1
                fps.append(fp)
                fails += fr is not None and (fp < 0 or fr < fp)
                lost += (s.lost + s.stuck) > 0
                own6.append(s.owner - s.cost)
            fps = np.array(fps)
            big = np.where(fps >= 0, fps, 10 ** 6)
            ix = lambda d: next(i for i, x in enumerate(cal) if x > d)   # noqa: E731
            res[side] = {"first_pay_med": _date(cal, np.median(big) if np.median(big) < LEN else None),
                         "first_pay_k_med": float(np.median(big)) + 1 if np.median(big) < LEN else None,
                         "first_pay_p10": _date(cal, np.percentile(big, 10)),
                         "first_pay_p90": _date(cal, np.percentile(big, 90) if np.percentile(big, 90) < LEN else None),
                         "p_by_dec31": round(100.0 * float(((fps >= 0) & (fps < ix("2026-12-31"))).mean()), 1),
                         "p_by_jan15": round(100.0 * float(((fps >= 0) & (fps < ix("2027-01-15"))).mean()), 1),
                         "p_no_pay_6m": round(100.0 * float((fps < 0).mean()), 1),
                         "p_lost_before_pay": round(100.0 * fails / n, 1), "lost_6m": round(100.0 * lost / n, 1),
                         "cash_m": round(float(np.mean(own6)) / MO)}
        out[sp] = res
        log(f"  L4 combo {sp}: after {res['after']} | now {res['now']}")
    return out


# ================================================================================================ the judge (design file)
def judge(base, var):
    """-> (pass?, reasons) on one account's stats per span (H2, H1, REF) from the design's fixed bar."""
    why, ok = [], True
    for sp in ("H2", "H1"):
        b, v = base[sp], var[sp]
        dj = v["p_by_jan15"] - b["p_by_jan15"]
        dk = (v["first_pay_k_med"] or 999) - (b["first_pay_k_med"] or 999)
        dl = v["p_lost_before_pay"] - b["p_lost_before_pay"]
        d6 = v["lost_6m"] - b["lost_6m"]
        if dj < 1.0:
            ok = False
            why.append(f"{sp}: paid by Jan 15 {b['p_by_jan15']:g}% -> {v['p_by_jan15']:g}% (needs +1 pt)")
        if dk > 0:
            ok = False
            why.append(f"{sp}: median first payout {dk:+.0f} trading days")
        if dl > 0.5:
            ok = False
            why.append(f"{sp}: lost before it pays {b['p_lost_before_pay']:g}% -> {v['p_lost_before_pay']:g}%")
        if d6 > 1.0:
            ok = False
            why.append(f"{sp}: lost in 6 months {b['lost_6m']:g}% -> {v['lost_6m']:g}%")
    dr = var["REF"]["p_lost_before_pay"] - base["REF"]["p_lost_before_pay"]
    if dr > 2.0:
        ok = False
        why.append(f"2021-25: lost before it pays {base['REF']['p_lost_before_pay']:g}% -> {var['REF']['p_lost_before_pay']:g}%")
    dm = var["H2"]["cash_m"] - base["H2"]["cash_m"]
    if dm < -25:
        ok = False
        why.append(f"H2: ${-dm:,} a month less")
    return ok, why


# ================================================================================================ main
def study(n=1000, only=None, log=print):
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    cal = calendar()
    S = SA.data()["S"]
    MP.by()
    res = {"v": 1, "date": TODAY, "start": START, "end": cal[LEN - 1], "n": n, "sessions": LEN, "closed": sorted(CLOSED),
           "markets": MP.MKT, "names": NAMES, "split": SPLIT, "tax": TAX, "design": "research/lab/payday_design_2026-11-20.md",
           "built_by": "tools/money/payday_plan.py", "rows": {}, "levers": {}}
    t0 = time.time()
    for sp in SPANS:
        paths = U.mc_paths(S, sp, n, length=LEN, seed=BL.A4.SEED_LIFE)
        R = run(paths, BASE)
        acc, fps = {}, []
        for k in KEYS:
            a, fp = acct(R[k], cal, k)
            acc[k], _ = a, fps.append(fp)
        res["rows"][sp] = {"accounts": acc, "fleet": fleet(fps, cal)}
        log(f"{sp} plan {time.time() - t0:.0f}s: any by Dec 31 {res['rows'][sp]['fleet']['p_any_by_dec31']}%, by Jan 15 "
            f"{res['rows'][sp]['fleet']['p_any_by_jan15']}%")
        for k, a in acc.items():
            log(f"   {k} med {a['first_pay_med']} ({a['first_pay_p10']} - {a['first_pay_p90']}) ${a['first_pay_usd']} "
                f"Dec31 {a['p_by_dec31']}% Jan15 {a['p_by_jan15']}% lost-first {a['p_lost_before_pay']}% lost6 {a['lost_6m']}% "
                f"${a['cash_m']}/mo funded {a.get('funded_med')}")
        if only == "plan":
            continue
        for lid, (tag, words, mk) in LEVERS.items():
            for k, maker in mk.items():
                V = run(paths, {k: maker})
                v, _ = acct(V[k], cal, k)
                res["levers"].setdefault(lid, {"tag": tag, "what": words, "accounts": {}})["accounts"].setdefault(k, {})[sp] = v
                log(f"   {tag} {lid} {k}: med {v['first_pay_med']} Jan15 {v['p_by_jan15']}% lost-first {v['p_lost_before_pay']}% "
                    f"lost6 {v['lost_6m']}% ${v['cash_m']}/mo ({time.time() - t0:.0f}s)")
    if only != "plan":
        cn = combo_now(min(n, 600), log)
        res["levers"]["combo50k-now"] = {"tag": "L4", "what": "ATLAS on Zlarior's 50K NOW at 50% in the eval (vs after the pass)",
                                         "engine": "tools/money/combo_account.py Slot from today's hole (week blocks, seed 202)",
                                         "accounts": {"Z50": {sp: cn[sp]["now"] for sp in SPANS}},
                                         "base_override": {"Z50": {sp: cn[sp]["after"] for sp in SPANS}}}
        for lid, L in res["levers"].items():
            verdicts = {}
            for k, var in L["accounts"].items():
                base = (L.get("base_override") or {}).get(k) or {sp: res["rows"][sp]["accounts"][k] for sp in SPANS}
                verdicts[k] = judge(base, var)
            L["pass"] = all(v[0] for v in verdicts.values())
            L["why"] = [w for v in verdicts.values() for w in v[1]]
            log(f"{L['tag']} {lid}: {'PASS' if L['pass'] else 'no'} {L['why'][:3]}")
    res["secs"] = round(time.time() - t0)
    return res


LOSSES = os.path.join(ROOT, "research", "lab", "payday_losses.json")
KEEP_L = ("first_pay_med", "first_pay_k_med", "p_by_dec31", "p_by_jan15", "p_lost_before_pay", "lost_6m", "cash_m")


def lab_rows(res=None, losses=None):
    """The Lab rows (research/lab/payday_levers.json, the lit_more_money.json row shape): the 8 levers + the 2 loss cuts."""
    res = res or json.load(open(OUT, encoding="utf-8"))
    rows = []
    for lid, L in res["levers"].items():
        per = {}
        for k, var in L["accounts"].items():
            base = (L.get("base_override") or {}).get(k) or {sp: res["rows"][sp]["accounts"][k] for sp in SPANS}
            per[k] = {sp: {"today": {x: base[sp].get(x) for x in KEEP_L}, "with": {x: var[sp].get(x) for x in KEEP_L}} for sp in SPANS}
        rows.append({"id": f"payday_{lid}", "bot": "money", "kind": "payday_lever", "tag": L["tag"], "title": L["what"],
                     "status": "passed" if L["pass"] else "rejected", "why": L["why"], "accounts": per,
                     "d_per_month": {sp: round(sum(per[k][sp]["with"]["cash_m"] - per[k][sp]["today"]["cash_m"] for k in per)) for sp in SPANS},
                     "gate": "both 2026 halves: paid by Jan 15 +1 pt and median first payout not later; lost before it pays "
                             "<= +0.5 pt, lost in 6 months <= +1 pt; 2021-25 lost before it pays <= +2 pts; Jul-Oct $ a month >= -$25",
                     "source": "tools/money/payday_plan.py, research/writeups/payday-plan-2026-11-20.md"})
    if losses is None and os.path.exists(LOSSES):
        losses = json.load(open(LOSSES, encoding="utf-8"))
    for cid, C in ((losses or {}).get("cuts") or {}).items():
        sp3 = ("H1", "H2", "2021-25")
        rows.append({"id": "payday_" + cid.split()[1], "bot": C["bot"], "kind": "loss_cut", "tag": cid.split()[0], "title": cid,
                     "status": "passed" if C["pass"] else "rejected", "why": C["why"],
                     "per_month": {sp: C["with_cut"][sp]["per_month"] for sp in sp3},
                     "d_per_month": {sp: C["with_cut"][sp]["per_month"] - C["today"][sp]["per_month"] for sp in sp3},
                     "tpw": {sp: C["with_cut"][sp]["tpw"] for sp in sp3}, "pf": {sp: C["with_cut"][sp]["pf"] for sp in sp3},
                     "dd": {sp: C["with_cut"][sp]["dd"] for sp in sp3}, "cut_trades": C["cut_trades"],
                     "a25_seat": C.get("a25_seat"),
                     "source": "tools/payday_losses.py, research/writeups/payday-plan-2026-11-20.md"})
    doc = {"v": 1, "date": TODAY, "kind": "payday_lever", "bot": "money",
           "about": "Payday plan levers (8) and loss cuts (2), pre-registered in research/lab/payday_design_2026-11-20.md; "
                    "judged on the first payout date AND the chance of losing the account",
           "count": len(rows), "passed": sum(1 for r in rows if r["status"] == "passed"), "rows": rows}
    with open(LAB, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, default=float)
    return LAB


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--only", default=None)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--lab", action="store_true", help="only rebuild the Lab rows from the saved results")
    ap.add_argument("--asof", default=None, help="start from a later board (ASOF keys, e.g. 2026-11-23)")
    a = ap.parse_args(argv)
    if a.asof:
        global TODAY, START, ZL, N25_S0, A25_STATE
        st = ASOF[a.asof]
        TODAY = START = a.asof
        ZL, N25_S0, A25_STATE = dict(st["zl"]), st["n25_s0"], dict(st["a25"])
    if a.lab:
        print("wrote", os.path.relpath(lab_rows(), ROOT))
        return 0
    res = study(a.n, a.only)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print("wrote", os.path.relpath(a.out, ROOT))
    if a.only != "plan" and a.out == OUT:
        print("wrote", os.path.relpath(lab_rows(res), ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
