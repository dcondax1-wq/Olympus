"""ONE account, several NQ bots (owner 2026-11-19: "What if we had one account trade a lot of times for NQ with multiple
strategies so it traded more frequent and very profitable. Figure it out; and whether we do a 25K or 50K Builder. Or maybe a
25K Rapid EOD - don't give me bullshit results."). Write-up: research/writeups/one-account-combo-2026-11-19.md.
PAPER RESEARCH ONLY: reads stored trades, writes research/lab/combo_account*.json, changes nothing live (no live_model*.json,
no engine file; the engine's own sizing functions are CALLED, never edited).

DESIGN (fixed and committed BEFORE the first full run; nothing below was changed after looking at a result)
---------------------------------------------------------------------------------------------------------------------------
Bots, exactly as they are today (no re-tuning, the repo's own trade generators; futures data only, CME NQ1! bars):
  Z  Zlarior / LIT   tools/account4_sim.load(): the 120 live-loop trades of 2026 (1m fills) + the 511 of 2021-25 (5m).
  A  ATLAS           the raw EMA / MACD / S-R member trades (tools/second_mix.units(), the stored research trades of
                     engine/second.py) with ATLAS's own rules: one position, max 2 entries a day, member order on a tie. NOT
                     the account_units version (that one is already cut around LIT; here the account rule below does it).
  B  BLITZ           today's rule ALONE (tools/blitz_review.sim(inputs(B, None)) = engine/blitz VERSION 2 without the
                     account-C blocking): 2026 on 1m, 2021-25 on 5m; its later-break size flag kept per trade.
  P  post-close follow (sensitivity rows only): tools/third_strategy cell pcm_k5_follow_or15_r2_x0925 (5m, 18:15-20:00
                     entries, out 09:25), the parked paper lead of research/writeups/third-strategy-2026-11-18.md.
  Costs: $1.90 a micro round trip + the repo's fills (1 tick on every market entry and every stop / market exit; limit
  entries / targets at the limit price). Sensitivity "+1 tick": one MORE tick on the entry AND the exit of every trade.
One account = one net NQ position (pre-declared rules):
  first-in (MAIN)    while any trade is open on the account, every later signal (either side) is skipped.
  adds (sensitivity) a later signal on the SAME side is added (contracts capped at the plan's max micros together, sized
                     from the room left after the open trades' full stop-outs); an opposite signal is skipped. Open
                     losses of overlapping trades are added worst-on-worst (conservative).
  Ties (same entry minute): Zlarior, then ATLAS, then BLITZ, then P.
Sizing, all bots on ONE shared room (balance + today's closed P&L - the trailing floor), capped by the plan's max micros:
  own (MAIN)  each bot keeps the size rule it trades with today, on this plan's numbers:
              Zlarior eval: the live two_week (room_f 0.4, one winner passes, kept to session 80; Builder 50K =
                live_model.json lit_sizing via tools/account4_sim.ecfg, other plans = the engine/multi_account preset);
                funded: the preset's funded rule (engine/multi_account: 60% of the room, <= $1,500 / $750, a winner
                <= $2,000 / $1,000)
              ATLAS: engine/account_b.qty / funded_qty on the plan (need size in the eval, the preset's funded rule, the
                soft-daily-loss guard, the zombie-eval last bullet; stops below $200 of eval room)
              BLITZ: engine/account_c.qty's rule (eval 40% of the room, the full room from session 5, <= $600, 0.9 x the
                day's loss left, later break x0.5 / x1.75; funded 10%, <= $150, no new trade after +$400 a day; stops
                below $249.56 of room); defined for a 25K, so x2 on a 50K plan
  lanes       the rule engine/rapid.py built for ONE account (and stack-one-account-2026-11-16.md): the FIRST bot of the
              combo (Zlarior > ATLAS > BLITZ) keeps its own size; every other bot risks min($cap, 30% of the room, the
              soft daily loss left) a trade: ATLAS $250, BLITZ $150, P $125 on a 25K (x2 on a 50K)
  Rapid EOD evals: the fleet's 30% best-day guard on every trade (a winner keeps the day <= 30% x target x 0.95).
Accounts (research/lit/mffu_rules.json + research/props/firm_rules.json via tools/account4_sim.rules; Rapid EOD 25K =
engine/rapid.PLANS + the plan page facts of rapid-25k-vs-50k-2026-11-17.md), the owner's CLUB prices:
  Builder 50K $91.80  $3,000 target, $2,000 EOD trailing (locks at +$100), $1,000 soft day, 40 micros, no best-day rule,
                      1 day; funded: $2,100 buffer, $500-$2,000, 50% best day a cycle, 2 days a cycle, 48 h wait, 80%,
                      5 payouts (engine/funded_life, tools/uprisk.Funded logic), the bot's ask line $1,500
  Builder 25K $63     $1,500, $1,000 EOD, $600 soft day, 20 micros; funded $1,100 buffer, $250-$1,000, 50%, 2 days, 80%,
                      5 payouts, ask line $750
  Rapid EOD 25K $97.20  $1,500, $1,000 EOD (open losses count), no daily loss (the bot's own $500), 20 micros, 30% best
                      day + 4 days in the eval; funded: daily payouts above $1,100, $500 min, >= $250 since the last, the
                      bot keeps $500 in, 90%, Tier-1 news flat -2/+2 min on the funded account only
  Rapid EOD 50K $165 (reference row)  $3,000, $2,000, the bot's $1,000 day, 30 micros, 30% + 4 days; funded $2,100
                      buffer, $500 min, >= $500 since, keeps $1,000, 90%, news rule
  Everyone flat by 15:55 ET (MFFU 16:10). The eval and the funded account fail on an intraday touch of the floor (open
  losses count); the soft day cuts a trade at its level. A funded account below its bots' stop-trading room is "stuck"
  (the bot stands down: counted with lost, a new eval is bought).
Monte Carlo: whole days drawn with replacement from the period (each day keeps its own trades together), the SAME paths for
every row; 2,000 paths x 126 sessions (6 months) for the account slot (eval -> 2 sessions paperwork -> funded -> lost /
stuck / 5 payouts -> buy the next eval: $ a month NET of every eval fee) and 2,000 x 126 from the first funded session.
Eval numbers = the first eval of each slot path (60-session horizon).
Periods judged SEPARATELY: H1 = 2026 Jan-Jun, H2 = 2026 Jul-Oct 16, REF = 2021-11 .. 2025.
Rows (all counted in the write-up): 7 combos (Z, A, B, Z+A, Z+B, A+B, Z+A+B) x 4 accounts, multi-bot combos in both
sizings; "Zlarior eval, combo once funded" (Z+A, Z+B, Z+A+B, both sizings); sensitivities: +1 tick (every main row), adds
(every multi-bot main row), P added to Z+A and Z+A+B (both sizings).
Verdict "beats today's setup on that account" (pre-registered): in EACH of H1, H2 AND 2021-25 the 6-month $ a month after
fees is higher by more than 2 paired standard errors, and the chance the 6 months lose money is not higher by more than
5 points; it must also stay higher (any margin) with +1 tick in all three periods. Today's setup: Builder 50K = Zlarior
alone; Builder 25K = Zlarior alone AND ATLAS alone (must beat both); Rapid EOD 25K = Zlarior + ATLAS, lanes (the preset
built for it); Rapid EOD 50K = Zlarior + ATLAS, lanes (reference).

    /home/user/heavy.sh python -X utf8 tools/money/combo_account.py build-blitz --tf 1     # BLITZ 2026 (1m) -> scratch part
    /home/user/heavy.sh python -X utf8 tools/money/combo_account.py build-blitz --tf 5     # BLITZ 2021-25 (5m)
    /home/user/heavy.sh python -X utf8 tools/money/combo_account.py build                  # all bots -> combo_account_trades.json
    /home/user/heavy.sh python -X utf8 tools/money/combo_account.py check                  # parity with the repo's simulators
    /home/user/heavy.sh python -X utf8 tools/money/combo_account.py study [--n 2000] [--workers 3]
Test: python -X utf8 -m tests.test_combo_account (money area).
"""
from __future__ import annotations

import argparse
import collections
import copy
import datetime as dt
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)

OUT = os.path.join(ROOT, "research", "lab", "combo_account.json")
TRADES = os.path.join(ROOT, "research", "lab", "combo_account_trades.json")
PART = os.path.join(ROOT, "research", "runs", "_cache", "combo_account_blitz_tf{tf}.json")
APATHS = os.path.join(ROOT, "research", "lab", "combo_atlas_paths.json")      # ATLAS's own intraday path (final study: early closes)
DATE = "2026-11-19"
PV, COMM, TICK = 2.0, 1.90, 0.25
SLIP = TICK
LEN, GAP, H_EVAL, MONTHS = 126, 2, 60, 6.0
SPAN = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16"), "REF": ("2021-11-01", "2025-12-31")}
SPAN_WORD = {"H1": "Jan-Jun 2026", "H2": "Jul-Oct 2026", "REF": "2021-25"}
SPANS = ("H1", "H2", "REF")
YEARS = {f"Y{y}": (f"{y}-01-01", f"{y}-12-31") for y in (2022, 2023, 2024, 2025)}     # honesty check only
ALL_SPANS = {**SPAN, **YEARS}
SEED_SLOT, SEED_FUND = 7, 23
N_PATHS = 2000
BEST_DAY_MARGIN = 0.95                      # engine/firms.BEST_DAY_MARGIN (the fleet's best-day guard)
STRATS = ("Z", "A", "B", "P")
NAME = {"Z": "Zlarior", "A": "ATLAS", "B": "BLITZ", "P": "post-close"}
PRIO = {s: i for i, s in enumerate(STRATS)}
PCM_CELL = {"k": 0.5, "dir": "follow", "trig": "or15", "tgt": "r2", "tx": "0925"}     # pcm_k5_follow_or15_r2_x0925
LANE_USD = {"A": 250.0, "B": 150.0, "P": 125.0}     # a 25K's lane $ (x2 on a 50K): engine/rapid ATLAS lane, stack BLITZ
LANE_F = 0.3
BLITZ_EVAL = {"f": 0.4, "cap": 600.0, "dll_frac": 0.9, "day_tp": None, "push_from": 5, "push_f": 1.0}   # engine/account_c
BLITZ_FUNDED = {"f": 0.1, "cap": 150.0, "dll_frac": 0.9, "day_tp": 400.0, "push_from": None, "push_f": None}
BLITZ_LATER = {"first_x": 0.5, "later_x": 1.75, "f_max": 1.0}
BLITZ_STUCK = 249.56                        # engine/blitz.STUCK_ROOM (25K)
PLANS = {
    "b50": {"label": "Builder 50K", "kind": "builder", "preset": "mffu_builder_50k", "ab": "builder50k", "fl": "builder50k",
            "price": 91.80, "x": 2.0, "soft": 1000.0},
    "b25": {"label": "Builder 25K", "kind": "builder", "preset": "mffu_builder_25k", "ab": "builder25k", "fl": "builder25k",
            "price": 63.00, "x": 1.0, "soft": 600.0},
    "r25": {"label": "Rapid EOD 25K", "kind": "rapid", "preset": "mffu_rapid_eod_25k", "ab": "rapideod25k", "price": 97.20,
            "x": 1.0, "soft": 500.0, "keep": 500.0, "since": 250.0},
    "r50": {"label": "Rapid EOD 50K (reference)", "kind": "rapid", "preset": "mffu_rapid_eod_50k", "ab": "rapideod50k",
            "price": 165.00, "x": 2.0, "soft": 1000.0, "keep": 1000.0, "since": 500.0},
}
ACCTS = ("b50", "b25", "r25", "r50")
COMBOS = ("Z", "A", "B", "Z+A", "Z+B", "A+B", "Z+A+B")
CURRENT = {"b50": [("Z", "own")], "b25": [("Z", "own"), ("A", "own")], "r25": [("Z+A", "lanes")], "r50": [("Z+A", "lanes")]}


def members(combo: str) -> tuple:
    return tuple(sorted(combo.split("+"), key=lambda s: PRIO[s]))


# ================================================================================================ build: the trades
def _f(x, nd=4):
    return None if x is None else round(float(x), nd)


def build_blitz(tf: int) -> str:
    """BLITZ today's rule alone on one timeframe (one process per timeframe: memory) -> a scratch part."""
    from tools import blitz_review as BR
    from tools import scalp_na_lib as N
    BR._ledger()
    B = N.bars(tf)
    T = BR.sim(B, BR.inputs(B, None))
    keep = (lambda d: d >= "2026-01-01") if tf == 1 else (lambda d: d < "2026-01-01")
    rows = []
    for t in T:
        if not keep(t["day"]):
            continue
        pts = float(t["pts"])
        rows.append({"s": "B", "day": t["day"], "et": int(t["entry_t"]), "xt": int(t["exit_t"]), "d": int(t["dir"]),
                     "risk": _f(t["risk_pts"]), "tgt": None, "pts": _f(pts), "w1": _f(min(0.0, -float(t["mae_pts"]), pts)),
                     "tf": tf, "src": "BLITZ", "lb": float(t["lb"]), "sm": 1.0, "x": t["exit_kind"]})
    p = PART.format(tf=tf)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(rows, fh)
    return p


def _lit_rows():
    import account4_sim as A4
    S, BY = A4.load()
    out = []
    for ts in BY:
        for t in ts:
            out.append({"s": "Z", "day": t["day"], "et": int(t["entry_t"]), "xt": int(t["exit_t"]), "d": int(t["dir"]),
                        "risk": _f(t["risk"]), "tgt": _f(t["tgt"]), "pts": _f(t["pts"]), "w1": _f(min(0.0, t["w1"])),
                        "tf": 5 if t["ref"] else 1, "src": "LIT", "lb": 1.0, "sm": float(t.get("size_mult", 1.0)), "x": t["exit"]})
    return out


def _atlas_rows():
    """ATLAS's raw members with its own rules (one position, max 2 a day), member order EMA, MD, SR on a tie."""
    from tools import second_mix as M
    U = M.units()
    pr = {"EMA": 0, "MD": 1, "SR": 2}
    allu = sorted([u for nm in ("EMA", "MD", "SR") for u in U[nm]], key=lambda t: (t["entry_t"], pr[t["src"]]))
    out, cur, busy, nday = [], None, 0, 0
    for t in allu:
        if t["day"] != cur:
            cur, busy, nday = t["day"], 0, 0
        if t["entry_t"] < busy or nday >= 2:
            continue
        busy, nday = t["exit_t"], nday + 1
        out.append({"s": "A", "day": t["day"], "et": int(t["entry_t"]), "xt": int(t["exit_t"]), "d": int(t["dir"]),
                    "risk": _f(t["risk"]), "tgt": _f(t["tgt"]), "pts": _f(t["pts"]), "w1": _f(min(0.0, t["w1"])),
                    "tf": 5, "src": t["src"], "lb": 1.0, "sm": 1.0, "x": t["exit"]})
    return out


def _pcm_rows():
    from tools import third_strategy as TS
    b = TS.B()
    W = TS.execute(TS.pcm(PCM_CELL))
    out = []
    for w in W:
        e0 = int(w["i"]) + 1
        j = e0 + int(w["bars"])
        xt = int(b.t[j]) if w["exit"] == "TIME" else int(b.t[min(j, len(b.t) - 1)]) + 300
        risk, pts = float(w["risk"]), float(w["pts"])
        out.append({"s": "P", "day": w["day"], "et": int(b.t[e0]), "xt": xt, "d": int(w["dir"]), "risk": _f(risk),
                    "tgt": _f(2.0 * risk), "pts": _f(pts), "w1": _f(max(-(risk + TICK), min(0.0, -float(w["mae"]) * risk, pts))),
                    "tf": 5, "src": "PCM", "lb": 1.0, "sm": 1.0, "x": w["exit"]})
    return out


def _news(rows):
    """The Rapid EOD funded Tier-1 rule (tools/money/stack_one_account.news_rule: flat -2 / +2 min of CPI, jobs, FOMC,
    minutes; an entry inside the window skipped, an open trade flattened at release - 2 min at that bar's open, 1 tick)."""
    import stack_one_account as SOA
    by = collections.defaultdict(list)
    for r in rows:
        by[r["day"]].append(r)
    for day, ts in by.items():
        conv = [{"day": r["day"], "entry_t": r["et"], "exit_t": r["xt"], "dir": r["d"], "pts": r["pts"], "w1": r["w1"],
                 "tf": r["tf"], "_k": i} for i, r in enumerate(ts)]
        got = {x["_k"]: x for x in SOA.news_rule(conv)}
        for i, r in enumerate(ts):
            x = got.get(i)
            if x is None:
                r["n"] = "skip"
            elif x.get("news"):
                r["n"] = [_f(x["pts"]), _f(x["w1"]), int(x["exit_t"])]
            else:
                r["n"] = None
    return rows


def build() -> dict:
    rows = _lit_rows() + _atlas_rows() + _pcm_rows()
    for tf in (1, 5):
        p = PART.format(tf=tf)
        if not os.path.exists(p):
            raise SystemExit(f"missing {p}: run build-blitz --tf {tf} first (one timeframe per process)")
        rows += json.load(open(p, encoding="utf-8"))
    rows = [r for r in rows if SPAN["REF"][0] <= r["day"] <= SPAN["H2"][1]]
    rows = _news(rows)
    rows.sort(key=lambda r: (r["day"], r["et"], PRIO[r["s"]]))
    cols = ["s", "day", "et", "xt", "d", "risk", "tgt", "pts", "w1", "tf", "src", "lb", "sm", "x", "n"]
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "cols": cols, "rows": [[r.get(c) for c in cols] for r in rows],
           "count": dict(collections.Counter(r["s"] for r in rows))}
    os.makedirs(os.path.dirname(TRADES), exist_ok=True)
    with open(TRADES, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    return out


# ================================================================================================ data in memory
_D = {}


def sessions():
    if "S" not in _D:
        import uprisk as U
        _D["S"] = U.sessions(SPAN["REF"][0], SPAN["H2"][1])
    return _D["S"]


def trades(path=None):
    """session index -> [trade] (every bot), entry order; each trade carries its engine-sizing dicts."""
    key = path or TRADES
    if _D.get("T_key") != key:
        d = json.load(open(key, encoding="utf-8"))
        cols = d["cols"]
        S = sessions()
        ix = {s: i for i, s in enumerate(S)}
        by = [[] for _ in S]
        for row in d["rows"]:
            r = dict(zip(cols, row))
            i = ix.get(r["day"])
            if i is None:
                continue
            r["sz"] = {"risk_pts": r["risk"], "tgt_pts": r["tgt"], "size_mult": float(r.get("sm") or 1.0)}
            r["sze"] = {"risk_pts": r["risk"], "tgt_pts": r["tgt"], "size_mult": 1.0}
            by[i].append(r)
        _D["T"], _D["T_key"] = by, key
        _D.pop("C", None)
    return _D["T"]


def _span_of(day):
    return next(s for s in SPANS if SPAN[s][0] <= day <= SPAN[s][1])


def _zero_shift(zero):
    """honesty placebo: per bot and period, its mean points-per-stop (R) on the stored trades; subtracting mean R x stop
    from every trade keeps the bot's timing, stops, win / loss shape and variance but takes its edge to zero."""
    out = {}
    for s in zero:
        for sp in SPANS:
            a, z = span_ix(sp)
            R = [t["pts"] / t["risk"] for i in range(a, z) for t in trades()[i] if t["s"] == s and t["risk"]]
            out[(s, sp)] = float(np.mean(R)) if R else 0.0
    return out


def combo_days(combo: str, news: bool = False, zero: tuple = (), drop=None) -> list:
    """per session: the combo's trades (the news-ruled versions for a Rapid funded account), entry order, Z > A > B > P.
    zero = bots taken to zero edge (honesty placebo only); drop = days whose ATLAS trades are removed (final study: ATLAS's
    best days taken away)."""
    zero = tuple(zero or ())
    drop = frozenset(drop or ())
    key = (combo, news, zero, drop)
    C = _D.setdefault("C", {})
    if key not in C:
        ms = set(members(combo))
        sh = _zero_shift(zero) if zero else {}
        out = []
        for ts in trades():
            day = []
            for t in ts:
                if t["s"] not in ms:
                    continue
                if drop and t["s"] == "A" and t["day"] in drop:
                    continue
                if news and t.get("n"):
                    if t["n"] == "skip":
                        continue
                    t = {**t, "pts": t["n"][0], "w1": t["n"][1], "xt": t["n"][2]}
                if t["s"] in zero:
                    p2 = t["pts"] - sh[(t["s"], _span_of(t["day"]))] * t["risk"]
                    t = {**t, "pts": p2, "w1": min(t["w1"], p2)}
                day.append(t)
            day.sort(key=lambda t: (t["et"], PRIO[t["s"]]))
            out.append(day)
        C[key] = out
    return C[key]


def span_ix(span):
    S = sessions()
    a, z = ALL_SPANS[span]
    ix = [i for i, d in enumerate(S) if a <= d <= z]
    return ix[0], ix[-1] + 1


def day_paths(span, n, length=LEN, seed=SEED_SLOT):
    """Whole days drawn with replacement from the period (a day keeps all its trades), the same paths for every row."""
    a, z = span_ix(span)
    return np.random.default_rng(seed).integers(a, z, size=(n, length))


# ================================================================================================ plan rules + sizing
_P = {}


def plan(acct: str) -> dict:
    """eval rules E, funded rules F, sizing configs of every bot on this plan (the engine's own configs, built once)."""
    if acct in _P:
        return _P[acct]
    import account4_sim as A4
    from engine import account_b as EAB
    from engine import funded_life as FL
    from engine import multi_account as MA
    P = dict(PLANS[acct])
    E, F = A4.rules(P["preset"])
    base = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
    E = {**E, "dll": P["soft"]} if P["kind"] == "rapid" else E
    P["E"] = E
    if acct == "b50":
        ze = A4.ecfg(A4.MFFU_E)                       # Zlarior's own 50K: live_model.json lit_sizing (two_week, room_f 0.4)
    else:
        ze = MA.sizing_cfg(base, MA.normalize({"id": "x", "preset": P["preset"], "mode": "two_week", "adapter": "paper"}))
    P["z_eval"] = {k: v for k, v in ze.items() if not str(k).startswith("_")}
    zf = MA.sizing_cfg(base, MA.normalize({"id": "x", "preset": P["preset"], "mode": "funded", "adapter": "paper"}))
    P["z_funded"] = dict(zf["funded"])
    spec = EAB.normalize({"account": "research", "plan": P["ab"], "eval_start": "2026-01-02"}, lit_account=None)
    assert not spec.get("problem"), spec.get("problem")
    P["a_spec"] = spec
    P["a_spec_f"] = {**spec, "stage": "funded", "funded": {"start": "2026-01-02", "balance": float(spec["rules"]["start"]),
                                                            "prior": 0.0, "payouts": {}}}
    if P["kind"] == "builder":
        fp = FL.plan_of(P["fl"])
        P["F"] = {"mll": fp["mll"], "lock": fp["lock"], "dll": fp["dll"], "buffer": fp["buffer"], "pay_min": fp["pay_min"],
                  "pay_max": fp["pay_max"], "split": fp["split"], "cons": fp["cons"], "cycle_days": int(fp["cycle_days"]),
                  "first_wait_h": fp["first_wait_h"], "max_payouts": int(fp["max_payouts"]), "maxq": int(fp["max_micros"]),
                  "ask_above": fp["ask_above"]}
    else:
        P["F"] = {"mll": F["mll"], "lock": F["lock"], "dll": P["soft"], "buffer": F["buffer"], "pay_min": F["pay_min"],
                  "pay_max": F["cap1"], "split": F["split"], "max_payouts": int(F["max_payouts"]), "maxq": int(F["maxq"]),
                  "keep": P["keep"], "since": P["since"]}
    P["acct_f"] = {"mll": P["F"]["mll"], "lock": P["F"]["lock"], "dll": P["F"]["dll"], "max_micros": P["F"]["maxq"],
                   "scale": 1.0, "cons": P["F"].get("cons") or 0.5, "buffer": P["F"]["buffer"],
                   "pay_max": min(P["F"]["pay_max"], 1e9)}
    _P[acct] = P
    return P


_CFG_CACHE = {}


def _patch_account_b():
    """engine/account_b rebuilds its sizing config from the preset on every call (fine live, slow in a Monte Carlo): cache
    it per plan + stage in THIS process only (same function, same answer; tests.test_combo_account checks the parity)."""
    from engine import account_b as EAB
    if getattr(EAB, "_combo_cached", False):
        return
    f1, f2 = EAB.sizing_cfg, EAB.funded_cfg

    def sizing_cfg(spec, base=None):
        k = ("e", spec.get("plan"), spec.get("eval_start"))
        if base is not None:
            return f1(spec, base)
        if k not in _CFG_CACHE:
            _CFG_CACHE[k] = f1(spec, base)
        return _CFG_CACHE[k]

    def funded_cfg(spec, base=None):
        k = ("f", spec.get("plan"))
        if base is not None:
            return f2(spec, base)
        if k not in _CFG_CACHE:
            _CFG_CACHE[k] = f2(spec, base)
        return _CFG_CACHE[k]
    EAB.sizing_cfg, EAB.funded_cfg, EAB._combo_cached = sizing_cfg, funded_cfg, True


def blitz_q(t, room, cum, session, P, stage):
    """engine/account_c.qty's rule on this plan's numbers ($ caps x2 on a 50K): eval 40% / the full room from session 5,
    <= $600, 0.9 x the soft day left, later break x0.5 / x1.75; funded 10%, <= $150, +$400 day stop."""
    from engine import account_c as AC
    x = P["x"]
    S = BLITZ_EVAL if stage == "eval" else BLITZ_FUNDED
    if room <= 0:
        return 0
    if S["day_tp"] is not None and cum >= S["day_tp"] * x:
        return 0
    risk_pm = (float(t["risk"]) + TICK) * PV + COMM
    f, cap = float(S["f"]), float(S["cap"]) * x
    if S["push_from"] and session >= S["push_from"]:
        f = float(S["push_f"])
    if stage == "eval":
        m = BLITZ_LATER["later_x"] if float(t.get("lb") or 0.5) > 1.0 else BLITZ_LATER["first_x"]
        f, cap = min(f * m, BLITZ_LATER["f_max"]), cap * m
    dll = P["E"]["dll"] if stage == "eval" else P["F"]["dll"]
    maxq = P["E"]["maxq"] if stage == "eval" else P["F"]["maxq"]
    return int(AC.frac_qty(risk_pm, room, cum, f, cap, float(dll), int(maxq), S["dll_frac"]))


def lane_q(t, s, room, cum, dll, maxq, x):
    """the one-account lane (engine/rapid ATLAS lane, stack_one_account.stack_q): min($cap, 30% of the room, the soft day
    left); micros = that / one full stop-out of 1 micro ((stop + 1 tick) x $2 + $1.90)."""
    loss1 = (float(t["risk"]) + SLIP) * PV + COMM
    usd = min(LANE_USD[s] * x, LANE_F * max(0.0, room), dll + min(0.0, cum))
    return max(0, min(int(maxq), int(usd // loss1)))


def min_room(s, stage, acct):
    """the room under which a bot stops trading (its own live line)."""
    x = PLANS[acct]["x"]
    if s == "B":
        return BLITZ_STUCK * x
    if stage == "funded":
        return 100.0
    if s == "A":
        return 200.0                                   # engine/account_b zombie-eval rule (eval_min_room)
    return 200.0 if x > 1 else 100.0                   # Zlarior: uprisk EPLAN / engine/rapid eval_min_room


# ================================================================================================ one account, one day
class Book:
    """ONE account (eval or funded) of one plan trading one combo, a session at a time. cell = {"acct", "sizing": "own" |
    "lanes", "rule": "first" | "adds", "ticks": extra ticks each way, "lit_funded": optional funded cfg override}."""

    def __init__(self, cell, stage, combo):
        from engine import sizing as SZ
        self.SZ = SZ
        self.cell, self.stage, self.combo = cell, stage, combo
        self.P = P = plan(cell["acct"])
        self.ms = members(combo)
        self.primary = self.ms[0]
        self.rule = cell.get("rule", "first")
        self.sizing = cell.get("sizing", "own")
        self.xt = float(cell.get("ticks", 0)) * TICK
        R = P["E"] if stage == "eval" else P["F"]
        self.R = R
        self.mll, self.lock, self.dll, self.maxq = float(R["mll"]), float(R["lock"]), float(R["dll"]), int(R["maxq"])
        self.bal, self.peak, self.floor = 0.0, 0.0, -self.mll
        self.s, self.dtr, self.best, self.wk = 0, 0, 0.0, {}
        self.max_risk, self.n_tr = 0.0, 0
        self.mr = {s: (-1e9 if cell.get("no_stuck") else min_room(s, stage, cell["acct"])) for s in self.ms}
        self.stuck_line = min(self.mr.values())
        self.cons = R.get("cons") if stage == "eval" else None
        self.state = "on"
        self.n_by = collections.Counter()
        # funded bookkeeping
        self.pays, self.cyc, self.cyc_start, self.k = [], [], 0.0, 0
        self.first_trade_k, self.elig_k = None, None
        self.zf = cell.get("lit_funded") or P["z_funded"]
        ze = cell.get("lit_eval")
        self.ze = {k: v for k, v in ze.items() if not str(k).startswith("_")} if ze else P["z_eval"]
        # final study (night-comboplus): the conflict rule, ATLAS's share of its own size, the eval guards
        self.conflict = cell.get("conflict") or "first"            # first | zprio (Z the other way closes A) | zfull (any Z closes A)
        af = cell.get("a_f") or {}
        self.a_f = float(af.get("eval" if stage == "eval" else "funded", 1.0))
        self.a_room_min = float(cell.get("a_room_min") or 0.0) if stage == "eval" else 0.0
        self.day_cap = float(cell.get("day_cap") or 0.0) if stage == "eval" else 0.0
        self.cuts = 0

    # -------------------------------------------------------------------- sizing
    def size(self, t, room, cum, st):
        s = t["s"]
        P, x = self.P, self.P["x"]
        if self.sizing == "lanes" and s != self.primary:
            return lane_q(t, s, room, cum, self.dll, self.maxq, x)
        if s == "P":
            return lane_q(t, s, room, cum, self.dll, self.maxq, x)
        if self.stage == "eval":
            if s == "Z":
                from engine.lit import qty_for
                m0 = qty_for(t["risk"])
                if not m0:
                    return 0
                return min(int(self.SZ.lit_qty(m0, t["sze"], self.ze, room=room, state=st, learning=None,
                                               max_micros=self.maxq)["qty"]), self.maxq)
            if s == "A":
                from engine import account_b as EAB
                return int(EAB.qty(P["a_spec"], t["sze"], st)["qty"])
            return blitz_q(t, room, cum, st["session"], P, "eval")
        if s == "Z":
            return min(int(self.SZ.funded_qty(t["sz"], st, self.zf, acct=P["acct_f"])), self.maxq)
        if s == "A":
            from engine import account_b as EAB
            return int(EAB.funded_qty(P["a_spec_f"], t["sze"], st)["qty"])
        return blitz_q(t, room, cum, st.get("session", 99), P, "funded")

    def cons_cap(self, q, t, cum):
        win1 = (t["tgt"] or 2.0 * t["risk"]) * PV - COMM
        if win1 <= 0:
            return q
        return min(q, int(math.floor((self.cons * self.R["tgt"] * BEST_DAY_MARGIN - max(0.0, cum)) / win1)))

    def state_for(self, room, cum, s):
        if self.stage == "eval":
            return {"profit": self.bal, "cum": cum, "room": room, "session": self.s, "n_today": self.n_by[s] if s == "A" else 0,
                    "wk_pnl": self.wk.get((self.s - 1) // 5, 0.0), "days_traded": self.dtr}
        F = self.P["F"]
        locked = self.floor >= self.lock - 1e-9 or bool(self.pays)
        cap = min(F["pay_max"], 2000.0) if self.P["kind"] == "rapid" else F["pay_max"]
        return {"room": room, "cum": cum, "locked": locked, "bal": self.bal, "session": 99, "n_today": self.n_by[s] if s == "A" else 0,
                "cycle_start_bal": round(self.cyc_start, 2), "cycle_prev": round(sum(self.cyc), 2),
                "best_prev": round(max(self.cyc), 2) if self.cyc else 0.0, "cycle_days_prev": len(self.cyc),
                "payouts_n": len(self.pays), "cycle_target": round(max(0.0, F["buffer"] + cap - self.cyc_start), 2)}

    # -------------------------------------------------------------------- the day's trades
    def trade_day(self, ts, keep=None):
        """-> (cum, traded, breached). The day's candidate trades in entry order on the account's one position."""
        floor = max(self.floor, self.lock) if (self.stage == "funded" and self.pays) else self.floor
        cum, traded = 0.0, False
        opn = []                                    # [exit_t, dir, micros, pnl, low, full stop-out $]
        self.n_by = collections.Counter()
        dll = self.dll
        for t in ts:
            et = t["et"]
            if opn:
                still = []
                for o in opn:
                    if o[0] <= et:
                        cum += o[3]
                    else:
                        still.append(o)
                opn = still
            if cum <= -dll:
                break
            if self.day_cap and cum <= -self.day_cap:                # eval guard: no new entry after a -$cap closed day
                break
            open_q = 0
            if opn:
                if self.rule != "adds" or any(o[1] != t["d"] for o in opn):
                    continue
                open_q = sum(o[2] for o in opn)
            o_loss = sum(o[5] for o in opn)
            o_low = sum(o[4] for o in opn)
            s = t["s"]
            room = round(self.bal + cum - floor - o_loss, 2)
            if room < self.mr[s]:
                continue
            if s == "A" and self.a_room_min and room < self.a_room_min:     # eval guard: ATLAS only with room >= X
                continue
            st = self.state_for(room, cum - o_loss, s)
            q = self.size(t, room, cum - o_loss, st)
            if s == "A" and self.a_f < 1.0 and q > 0:                       # ATLAS's share of its own size
                q = max(1, int(math.floor(self.a_f * q + 1e-9)))
            q = min(q, self.maxq - open_q)
            if q > 0 and self.cons:
                q = self.cons_cap(q, t, cum)
            if q <= 0:
                continue
            if s == "A" and self.conflict in ("zprio", "zfull"):
                t = self._maybe_cut(t, ts)
            traded = True
            self.n_by[s] += 1
            self.n_tr += 1
            pts = t["pts"] - 2.0 * self.xt
            w1 = min(t["w1"] - self.xt, pts)
            pnl = pts * PV * q - COMM * q
            low = min(0.0, w1 * PV * q - COMM * q, pnl)
            self.max_risk = max(self.max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + o_low + low <= -dll:                       # the soft day cuts the trade at its level
                pnl = -dll - cum - o_low - SLIP * PV * q
                low = pnl
            if self.bal + cum + o_low + low <= floor:
                if keep is not None:
                    keep.append((t, q, round(floor - self.bal - cum, 2)))
                return round(floor - self.bal, 2), traded, True
            if keep is not None:
                keep.append((t, q, round(pnl, 2)))
            opn.append([t["xt"], t["d"], q, pnl, low, (t["risk"] + SLIP + self.xt) * PV * q + COMM * q])
        for o in opn:
            cum += o[3]
        return cum, traded, False

    def _maybe_cut(self, t, ts):
        """Zlarior priority (final study): the first Zlarior signal while this ATLAS trade is open (the other way for zprio,
        either way for zfull) closes ATLAS at market at that minute; Zlarior then trades from the room after that close."""
        for z in ts:
            if z["et"] <= t["et"] or z["s"] != "Z":
                continue
            if z["et"] >= t["xt"]:
                break
            if self.conflict == "zfull" or z["d"] != t["d"]:
                self.cuts += 1
                return cut_trade(t, z["et"])
        return t


class Eval(Book):
    """tools/account4_sim.Ev's rules (bit-checked in check()): pass = target, min days, best day <= share of the profit."""

    def __init__(self, cell, combo):
        super().__init__(cell, "eval", combo)

    def step(self, ts, keep=None):
        E = self.R
        self.s += 1
        cum, traded, br = self.trade_day(ts, keep)
        if br:
            return "fail", cum
        self.bal += cum
        wkey = (self.s - 1) // 5
        self.wk[wkey] = self.wk.get(wkey, 0.0) + cum
        if traded:
            self.dtr += 1
            self.best = max(self.best, cum)
        if self.bal <= self.floor:
            return "fail", round(cum, 2)
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - self.mll), self.lock)
        if self.bal >= E["tgt"] and self.dtr >= E.get("min_days", 1) and (not E.get("cons") or self.best <= E["cons"] * self.bal + 1e-9):
            return "pass", round(cum, 2)
        if self.bal - self.floor < self.stuck_line:
            return "stuck", round(cum, 2)
        return None, round(cum, 2)


class Funded(Book):
    """MFFU sim funded. Builder: tools/uprisk.Funded's fast path (buffer, $min-$max, 50% best day a cycle, 2 days a cycle,
    48 h after the first trade, the bot's ask line, floor locked at +$100 after the first payout, 5 payouts). Rapid EOD:
    tools/money/rapid_levers.Rapid ("cushion": daily, above buffer + keep, $500 min, >= since-rule, 90%)."""

    def __init__(self, cell, combo):
        super().__init__(cell, "funded", combo)
        self.max_pays = int(self.P["F"]["max_payouts"])

    def _pay(self, k):
        return self._builder_pay(k) if self.P["kind"] == "builder" else self._rapid_pay()

    def step(self, ts, keep=None):
        """-> (event, owner $) with event None | "paid" | "lost" | "stuck" | "grad"."""
        if self.state != "on":
            return None, 0.0
        F = self.P["F"]
        k = self.k
        self.k += 1
        cum, traded, br = self.trade_day(ts, keep)
        if br:
            self.state = "lost"
            return "lost", 0.0
        if abs(cum) > 1e-9:
            self.bal += round(cum, 2)
            self.cyc.append(round(cum, 2))
            if self.first_trade_k is None:
                self.first_trade_k = k
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - self.mll), self.lock)
        ev, owner = None, 0.0
        amt = self._pay(k)
        if amt:
            self.pays.append(amt)
            self.bal -= amt
            self.cyc, self.cyc_start = [], self.bal
            owner = amt * F["split"]
            ev = "paid"
            if self.max_pays and len(self.pays) >= self.max_pays:
                self.state = "grad"
                return "grad", owner
        fl = max(self.floor, self.lock) if self.pays else self.floor
        if self.bal - fl < self.stuck_line:
            self.state = "stuck"
            return ("stuck" if ev is None else ev), owner
        return ev, owner

    def _builder_pay(self, k):
        F = self.P["F"]
        if self.first_trade_k is None:
            return 0.0
        if self.elig_k is None:
            self.elig_k = _elig_session(self.first_trade_k, F["first_wait_h"])
        cprof = round(sum(self.cyc), 2)
        best = round(max(self.cyc), 2) if self.cyc else 0.0
        cons_ok = cprof > 0 and best <= float(F["cons"]) * cprof + 1e-9
        above = round(self.bal - F["buffer"], 2)
        if k < self.elig_k or above < F["pay_min"] or len(self.cyc) < F["cycle_days"] or not cons_ok:
            return 0.0
        if above < F["ask_above"]:
            return 0.0
        return round(min(F["pay_max"], above), 2)

    def _rapid_pay(self):
        F = self.P["F"]
        avail = self.bal - F["buffer"] - F["keep"]
        since = self.bal - self.cyc_start if self.pays else self.bal
        if avail >= F["pay_min"] and since >= F["since"] - 1e-9:
            return round(min(F["pay_max"], avail), 2)
        return 0.0


_ELIG = {}


def _elig_session(k0, wait_h):
    """tools/uprisk.Funded's eligibility day (engine/funded_life: the next weekday >= 48 h after the first funded trade)
    on its synthetic weekday calendar, as a session index."""
    key = (k0, wait_h)
    if key not in _ELIG:
        import uprisk as U
        from engine import funded_life as FL
        d = FL._next_weekday(FL._add_days(U.cal(k0), int(math.ceil(wait_h / 24.0))))
        k = k0
        while U.cal(k) < d:
            k += 1
        _ELIG[key] = k
    return _ELIG[key]


# ================================================================================================ final study: live account, early closes
# MFFU Builder: after the 5th approved sim payout you move to a LIVE account and the sim accounts go dormant
# (research/lit/mffu_rules.json builder_50k.sim_funded.max_sim_payouts / sim_live_together; .live = the live rules).
# Confirmed: $2,000 EOD trailing that stops at the start once the floor gets there, $1,000 soft day, daily payouts >= $250,
# 80%, no consistency rule, 21 days with no evals after a live breach. Assumed (stated in the write-up): starts at $0
# profit, 40 micros, the bots size it with their funded rules, the bot keeps a $2,000 cushion and withdraws the rest.
LIVE = {"mll": 2000.0, "lock": 0.0, "dll": 1000.0, "maxq": 40, "pay_min": 250.0, "keep": 2000.0, "split": 0.8,
        "cooldown": 15, "gap": GAP}


class Live(Funded):
    """the live account after the 5th sim payout (final study main model): the funded Book on the live rules above."""

    def __init__(self, cell, combo):
        super().__init__(cell, combo)
        L = LIVE
        self.mll, self.lock, self.dll, self.maxq = L["mll"], L["lock"], L["dll"], int(L["maxq"])
        self.floor = -self.mll
        self.max_pays = None

    def state_for(self, room, cum, s):
        st = super().state_for(room, cum, s)
        st["cycle_target"] = None                     # no consistency rule on live: the size's best-day-share cap is off
        st["locked"] = self.floor >= self.lock - 1e-9 or bool(self.pays)
        return st

    def _pay(self, k):
        avail = round(self.bal - LIVE["keep"], 2)
        if self.floor >= self.lock - 1e-9 and avail >= LIVE["pay_min"]:
            return avail
        return 0.0


_AP = {}


def atlas_paths(path=None):
    """(day, entry, dir, member) -> (bar-close times, open points at each close, worst points so far): ATLAS's OWN stored
    path (tools/second_mix units), used only to price an ATLAS trade a conflict rule closes early."""
    key = path or APATHS
    if _AP.get("key") != key:
        d = json.load(open(key, encoding="utf-8"))
        P = {}
        for k, (dt_, po, pw) in d["paths"].items():
            day, et, dr, src = k.split("|")
            et = int(et)
            P[(day, et, int(dr), src)] = ([et + int(x) for x in dt_], [float(x) for x in po], [float(x) for x in pw])
        _AP.update(key=key, P=P)
    return _AP["P"]


def cut_trade(t, at):
    """ATLAS closed at market at minute `at`: the last bar close at or before it, minus 1 tick; its worst open loss up to
    then; inside its first bar: the entry price minus 1 tick (no look-ahead)."""
    import bisect
    pt, po, pw = atlas_paths()[(t["day"], int(t["et"]), int(t["d"]), t["src"])]
    k = bisect.bisect_right(pt, at) - 1
    if k >= 0:
        pts = po[k] - TICK
        w1 = min(0.0, pw[k], pts)
    else:
        pts = w1 = -TICK
    return {**t, "pts": round(pts, 4), "w1": round(min(w1, pts), 4), "xt": int(at), "cut": 1}


def build_paths(units=None) -> str:
    """research/lab/combo_atlas_paths.json from the second_mix units cache (every ATLAS row of the trade table)."""
    import pickle
    cands = [units, os.path.join(ROOT, "research", "runs", "_cache", "second_mix_units.pkl"),
             "/home/user/nq-liquidity-engine/research/runs/_cache/second_mix_units.pkl"]
    src = next(c for c in cands if c and os.path.exists(c))
    U = pickle.load(open(src, "rb"))
    by = {(u["day"], int(u["entry_t"]), int(u["dir"]), u["src"]): u for nm in ("EMA", "MD", "SR") for u in U[nm]}
    d = json.load(open(TRADES, encoding="utf-8"))
    cols = d["cols"]
    out, miss, bad = {}, 0, 0
    for row in d["rows"]:
        r = dict(zip(cols, row))
        if r["s"] != "A":
            continue
        u = by.get((r["day"], int(r["et"]), int(r["d"]), r["src"]))
        if u is None:
            miss += 1
            continue
        if abs(float(u["pts"]) - float(r["pts"])) > 1e-3 or abs(float(u["risk"]) - float(r["risk"])) > 1e-3:
            bad += 1
        out[f"{r['day']}|{int(r['et'])}|{int(r['d'])}|{r['src']}"] = [[int(x) - int(r["et"]) for x in u["pt"]],
                                                                       [round(float(x), 2) for x in u["po"]],
                                                                       [round(float(x), 2) for x in u["pw"]]]
    o = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "source": "tools/second_mix units (second_mix_units.pkl)",
         "note": "per ATLAS row: [bar-close time - entry (s)], [open points at that close], [worst points so far]",
         "missing": miss, "pts_mismatch": bad, "paths": out}
    with open(APATHS, "w", encoding="utf-8") as fh:
        json.dump(o, fh, separators=(",", ":"))
    return f"{len(out)} paths, {miss} missing, {bad} mismatched -> {os.path.relpath(APATHS, ROOT)}"


# ================================================================================================ the 6-month account slot
def row_key(r):
    k = f"{r['acct']}|{r['eval']}>{r['funded']}|{r['sizing']}|{r['rule']}|t{r['ticks']}"
    return k + (f"|zero{''.join(r['zero'])}" if r.get("zero") else "")


class Slot:
    """eval -> GAP sessions of paperwork -> funded -> lost / stuck / graduated -> buy the next eval (tools/account4_sim.Slot)."""

    def __init__(self, r):
        self.r = r
        self.cell = cell_of(r)
        self.price = PLANS[r["acct"]]["price"]
        self.cost = self.owner = 0.0
        self.evals = self.funded_n = self.lost = self.stuck = self.grads = self.pays = 0
        self.first_pay = None
        self.first_eval = None                     # (outcome, sessions)
        self.e = self.f = None
        self.wait = 0
        self.ek = 0
        self.max_risk = 0.0
        # after the 5th payout: "rebuy" = a new eval (the study), "stop" = the slot ends (live worth $0), "live" = MFFU's
        # move to a live account (sim dormant: no new eval while it trades; a live breach = 15 sessions, then a new eval)
        self.live_mode = r.get("live", "rebuy")
        self.lv, self.lv_wait, self.cool, self.done = None, 0, 0, False
        self.lives, self.owner_live = 0, 0.0
        self._buy()

    def _buy(self):
        self.cost += self.price
        self.evals += 1
        self.e = Eval(self.cell, self.r["eval"])
        self.ek = 0

    def step(self, k, ts_e, ts_f):
        if self.done:
            return
        if self.lv_wait:
            self.lv_wait -= 1
            if self.lv_wait <= 0:
                self.lv = Live(self.cell, self.r["funded"])
                self.lives += 1
            return
        if self.lv is not None:
            ev, x = self.lv.step(ts_f)
            self.max_risk = max(self.max_risk, self.lv.max_risk)
            if x:
                self.owner += x
                self.owner_live += x
                self.pays += 1
            if ev in ("lost", "stuck"):
                self.lost += ev == "lost"
                self.stuck += ev == "stuck"
                self.lv, self.cool = None, LIVE["cooldown"]
            return
        if self.cool:
            self.cool -= 1
            if self.cool <= 0:
                self._buy()
            return
        if self.e is not None:
            self.ek += 1
            res, _ = self.e.step(ts_e)
            self.max_risk = max(self.max_risk, self.e.max_risk)
            if res is None and self.first_eval is None and self.ek >= H_EVAL:
                self.first_eval = ("open", self.ek)
            if res == "pass":
                if self.first_eval is None:
                    self.first_eval = ("pass", self.ek)
                self.e, self.wait = None, GAP
            elif res in ("fail", "stuck"):
                if self.first_eval is None:
                    self.first_eval = ("fail", self.ek)
                self._buy()
            return
        if self.f is None:
            self.wait -= 1
            if self.wait <= 0:
                self.f = Funded(self.cell, self.r["funded"])
                self.funded_n += 1
            return
        ev, x = self.f.step(ts_f)
        self.max_risk = max(self.max_risk, self.f.max_risk)
        if x:
            self.owner += x
            self.pays += 1
            self.first_pay = self.first_pay or k + 1
        if ev in ("lost", "stuck", "grad"):
            self.lost += ev == "lost"
            self.stuck += ev == "stuck"
            self.grads += ev == "grad"
            self.f = None
            if ev == "grad" and self.live_mode == "stop":
                self.done = True
            elif ev == "grad" and self.live_mode == "live":
                self.lv_wait = LIVE["gap"]
            else:
                self._buy()

    def out(self):
        fe = self.first_eval or ("open", self.ek)
        return (self.owner - self.cost, self.owner, self.cost, self.evals, self.funded_n, self.lost + self.stuck, self.pays,
                self.first_pay or 0, fe[0], fe[1], self.max_risk, self.lives, self.owner_live, self.grads)


def is_rapid(acct):
    return PLANS[acct]["kind"] == "rapid"


def cell_of(r):
    """the Book's cell from a row (the final study's conflict / ATLAS share / eval guards ride along when present)."""
    c = {"acct": r["acct"], "sizing": r["sizing"], "rule": r["rule"], "ticks": r["ticks"]}
    for k in ("conflict", "a_f", "a_room_min", "day_cap"):
        if r.get(k) is not None:
            c[k] = r[k]
    return c


def run_slot(r, paths):
    De = combo_days(r["eval"], zero=r.get("zero"), drop=r.get("drop"))
    Df = combo_days(r["funded"], news=is_rapid(r["acct"]), zero=r.get("zero"), drop=r.get("drop"))
    out = []
    for seq in paths:
        s = Slot(r)
        for k, si in enumerate(seq):
            s.step(k, De[si], Df[si])
        out.append(s.out())
    return out


def run_funded(r, paths):
    Df = combo_days(r["funded"], news=is_rapid(r["acct"]), zero=r.get("zero"), drop=r.get("drop"))
    cell = cell_of(r)
    out = []
    for seq in paths:
        f = Funded(cell, r["funded"])
        owner, first, end, kind, n = 0.0, 0, 0, "", 0
        for k, si in enumerate(seq):
            ev, x = f.step(Df[si])
            if x:
                owner += x
                n += 1
                first = first or k + 1
            if ev in ("lost", "stuck", "grad"):
                end, kind = k + 1, ev
                break
        out.append((owner, first, end, kind, n))
    return out


# ================================================================================================ scores
def _pct(x, n):
    return round(100.0 * x / max(1, n), 1)


def slot_stats(R):
    a = np.array([x[0] for x in R]) / MONTHS
    n = len(R)
    fe = [(x[8], x[9]) for x in R]
    pas = [k for o, k in fe if o == "pass" and k <= H_EVAL]
    fp = [x[7] for x in R if x[7]]
    return {"net_m": round(float(a.mean())), "se_m": round(float(a.std(ddof=1) / math.sqrt(n)), 1),
            "p10_m": round(float(np.percentile(a, 10))), "p50_m": round(float(np.percentile(a, 50))),
            "p90_m": round(float(np.percentile(a, 90))), "p_neg": _pct(int((a < 0).sum()), n),
            "owner_m": round(float(np.mean([x[1] for x in R])) / MONTHS), "fees_6m": round(float(np.mean([x[2] for x in R])), 1),
            "evals": round(float(np.mean([x[3] for x in R])), 2), "funded": round(float(np.mean([x[4] for x in R])), 2),
            "lost": round(float(np.mean([x[5] for x in R])), 2), "p_no_pay": _pct(sum(1 for x in R if x[6] == 0), n),
            "first_pay_med": float(np.median(fp)) if fp else None,
            "first_pay_q": [float(np.percentile(fp, 25)), float(np.percentile(fp, 75))] if fp else None,
            "eval": {"p10": _pct(sum(1 for o, k in fe if o == "pass" and k <= 10), n),
                     "f10": _pct(sum(1 for o, k in fe if o == "fail" and k <= 10), n),
                     "p60": _pct(len(pas), n), "f60": _pct(sum(1 for o, k in fe if o == "fail" and k <= H_EVAL), n),
                     "pass_med": float(np.median(pas)) if pas else None,
                     "pass_q": [float(np.percentile(pas, 25)), float(np.percentile(pas, 75))] if pas else None},
            "max_risk": round(max(x[10] for x in R))}


def funded_stats(R):
    n = len(R)
    own = np.array([x[0] for x in R]) / MONTHS
    fr = [x[1] for x in R if x[1]]
    return {"per_month": round(float(own.mean())), "p10_m": round(float(np.percentile(own, 10))),
            "p90_m": round(float(np.percentile(own, 90))),
            "pay30": _pct(sum(1 for x in R if x[1] and x[1] <= 30), n), "pay60": _pct(sum(1 for x in R if x[1] and x[1] <= 60), n),
            "first_med": float(np.median(fr)) if fr else None,
            "lost": _pct(sum(1 for x in R if x[3] == "lost"), n), "lost_or_stuck": _pct(sum(1 for x in R if x[3] in ("lost", "stuck")), n),
            "grad": _pct(sum(1 for x in R if x[3] == "grad"), n), "payouts": round(float(np.mean([x[4] for x in R])), 2),
            "no_pay": _pct(sum(1 for x in R if not x[1]), n)}


def plain_stats(combo, span, rule="first", ticks=0, usd=250.0):
    """The period's REAL days in order, every taken trade at a fixed $ risk (min 1 micro, max 20), the one-position rule,
    costs in: what the trades themselves do, before any account rule."""
    D = combo_days(combo)
    a, z = span_ix(span)
    xt = ticks * TICK
    pnl, days, by = [], [], collections.Counter()
    for si in range(a, z):
        d, opn = 0.0, []
        for t in D[si]:
            opn = [o for o in opn if o[0] > t["et"]]
            if opn and (rule != "adds" or any(o[1] != t["d"] for o in opn)):
                continue
            q = max(1, min(20, int(usd // ((t["risk"] + SLIP) * PV + COMM))))
            p = (t["pts"] - 2 * xt) * PV * q - COMM * q
            pnl.append(p)
            by[t["s"]] += 1
            d += p
            opn.append((t["xt"], t["d"]))
        days.append(d)
    p = np.array(pnl) if pnl else np.zeros(1)
    eq = np.cumsum(days)
    gl = -p[p < 0].sum()
    ns = z - a
    return {"trades": len(pnl), "tpw": round(len(pnl) / (ns / 5.0), 2), "by": dict(by), "win": round(100.0 * float((p > 0).mean()), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (ns / 21.0)),
            "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())) if len(eq) else 0,
            "win_days_pw": round(sum(1 for x in days if x > 0) / (ns / 5.0), 2), "sessions": ns}


# ================================================================================================ the rows (fixed before the run)
def R(acct, ev, fu=None, sizing="own", rule="first", ticks=0, group="main"):
    return {"acct": acct, "eval": ev, "funded": fu or ev, "sizing": sizing, "rule": rule, "ticks": ticks, "group": group}


def rows():
    out = []
    for a in ACCTS:
        for c in COMBOS:
            multi = "+" in c
            for sz in (("own", "lanes") if multi else ("own",)):
                out.append(R(a, c, sizing=sz))
                out.append(R(a, c, sizing=sz, ticks=1, group="tick"))
                if multi:
                    out.append(R(a, c, sizing=sz, rule="adds", group="adds"))
        for c in ("Z+A", "Z+B", "Z+A+B"):
            for sz in ("own", "lanes"):
                out.append(R(a, "Z", c, sizing=sz, group="funded_only"))
        for c in ("Z+A+P", "Z+A+B+P"):
            for sz in ("own", "lanes"):
                out.append(R(a, c, sizing=sz, group="pcm"))
    return out


def score_row(r, n=N_PATHS, spans=SPANS):
    o = {}
    for sp in spans:
        PS = day_paths(sp, n, seed=SEED_SLOT)
        PF = day_paths(sp, n, seed=SEED_FUND)
        sl = run_slot(r, PS)
        fu = run_funded(r, PF)
        o[sp] = {"slot": slot_stats(sl), "funded": funded_stats(fu), "_net": np.array([x[0] for x in sl]) / MONTHS}
    return o


def _job(args):
    r, n = args[:2]
    _patch_account_b()
    t0 = time.time()
    o = score_row(r, n, *(args[2:] or ()))
    return row_key(r), o, round(time.time() - t0, 1)


def paired(a, b):
    d = a - b
    return float(d.mean()), float(d.std(ddof=1) / math.sqrt(len(d)))


def verdict(res, rows_):
    """The pre-registered rule (docstring): per account, every multi-bot row of the MAIN / funded-only groups vs today's
    setup, in H1, H2 AND 2021-25; then the same row at +1 tick must still be above (any margin)."""
    by = {row_key(r): r for r in rows_}
    out = {}
    for a in ACCTS:
        base_keys = [row_key(R(a, c, sizing=sz)) for c, sz in CURRENT[a]]
        for k, r in by.items():
            if r["acct"] != a or r["group"] not in ("main", "funded_only") or k in base_keys:
                continue
            if "+" not in r["eval"] and "+" not in r["funded"] and r["group"] == "main":
                continue
            chk, ok = {}, True
            for sp in SPANS:
                cs = []
                for bk in base_keys:
                    m, se = paired(res[k][sp]["_net"], res[bk][sp]["_net"])
                    dneg = res[k][sp]["slot"]["p_neg"] - res[bk][sp]["slot"]["p_neg"]
                    good = m > 2.0 * se and dneg <= 5.0
                    cs.append({"vs": bk, "gap_m": round(m), "se": round(se, 1), "p_neg_gap": round(dneg, 1), "ok": good})
                    ok = ok and good
                chk[sp] = cs
            tk = row_key({**r, "ticks": 1})
            tick_ok = None
            if tk in res:
                tick_ok = all(res[tk][sp]["slot"]["net_m"] > max(res[bk][sp]["slot"]["net_m"] for bk in base_keys) for sp in SPANS)
                ok = ok and tick_ok
            out[k] = {"beats_today": ok, "checks": chk, "plus1tick_still_above": tick_ok}
    return out


def study(n=N_PATHS, workers=3, only=None, log=print):
    trades()
    _patch_account_b()
    rs = rows()
    if only:
        rs = [r for r in rs if only(r)]
    log(f"{len(rs)} rows x {len(SPANS)} periods, {n} paths each (slot + funded)")
    res, secs = {}, {}
    jobs = [(r, n) for r in rs]
    t0 = time.time()
    if workers > 1:
        import multiprocessing as mp
        with mp.get_context("fork").Pool(workers) as pool:
            for i, (k, o, s) in enumerate(pool.imap_unordered(_job, jobs)):
                res[k], secs[k] = o, s
                log(f"[{i + 1}/{len(jobs)}] {k} {s:.0f}s ({time.time() - t0:.0f}s)")
    else:
        for i, j in enumerate(jobs):
            k, o, s = _job(j)
            res[k], secs[k] = o, s
            log(f"[{i + 1}/{len(jobs)}] {k} {s:.0f}s")
    plain = {}
    for c in sorted({r["eval"] for r in rs} | {r["funded"] for r in rs}):
        for rule in ("first", "adds"):
            for tk in (0, 1):
                plain[f"{c}|{rule}|t{tk}"] = {sp: plain_stats(c, sp, rule, tk) for sp in SPANS}
    v = verdict(res, rs)
    out = {"date": DATE, "n": n, "spans": SPAN, "plans": {a: {k: PLANS[a][k] for k in ("label", "price")} for a in ACCTS},
           "current": {a: [row_key(R(a, c, sizing=sz)) for c, sz in CURRENT[a]] for a in ACCTS},
           "rows": {row_key(r): {**r, **{sp: {kk: vv for kk, vv in res[row_key(r)][sp].items() if not kk.startswith("_")}
                                          for sp in SPANS}} for r in rs},
           "plain": plain, "verdict": v, "compared": {"rows": len(rs), "periods": len(SPANS), "cells": len(rs) * len(SPANS),
                                                      "verdict_candidates": len(v)},
           "secs": secs, "trades_count": json.load(open(TRADES, encoding="utf-8"))["count"]}
    return out


# ================================================================================================ parity with the repo's simulators
def check(n=150, log=print):
    """My Book == the repo's bit-checked simulators on the SAME paths, for the cases they cover:
      a. Zlarior alone, Builder 50K eval == tools/account4_sim.Ev (A4.ecfg(MFFU_E)) session for session
      b. Zlarior alone, Builder 50K / 25K funded with uprisk's UP50 / UP25 == tools/uprisk.Funded (payout $, sessions, lost)
      c. Zlarior alone, Rapid EOD 25K funded (UP25, keep $500) == tools/money/rapid_levers.Rapid
      d. the cached engine/account_b config gives the same micros as the uncached call."""
    import account4_sim as A4
    import uprisk as U
    trades()
    S = sessions()
    S4, BY4 = A4.load()
    assert S4 == S, "session lists differ"
    res = {}
    # a
    P = day_paths("H1", n, length=60)
    bad = 0
    De = combo_days("Z")
    for seq in P:
        a, b = A4.Ev(A4.ecfg(A4.MFFU_E), A4.MFFU_E), Eval(R("b50", "Z"), "Z")
        for si in seq:
            ra, pa = a.step(BY4[si])
            rb, pb = b.step(De[si])
            if ra != rb or abs(pa - pb) > 0.02:
                bad += 1
                break
            if ra:
                break
    res["a_eval_b50"] = bad
    # b
    for acct, plan_k, cfg in (("b50", "builder50k", U.UP50), ("b25", "builder25k", U.UP25)):
        bad = 0
        Df = combo_days("Z")
        for seq in day_paths("H2", n, length=LEN, seed=SEED_FUND):
            f0 = U.Funded(plan_k, cfg)
            f1 = Funded({**R(acct, "Z"), "lit_funded": cfg, "no_stuck": True}, "Z")   # uprisk has no stuck line
            for si in seq:
                e0, x0 = f0.step(BY4[si])
                e1, x1 = f1.step(Df[si])
                x0 = x0 or 0.0
                if (e0 or None) != (e1 if e1 != "paid" or x1 else None) or abs(x0 - x1) > 0.02:
                    bad += 1
                    break
                if e0 in ("lost", "grad"):
                    break
        res[f"b_funded_{acct}"] = bad
    # c
    import rapid_levers as RL
    import rapid25 as R25
    E, F = R25.rules("25k")
    bad = 0
    Df = combo_days("Z", news=True)
    import stack_one_account as SOA
    BYn = [SOA.news_rule([{**t, "strat": "LIT", "tf": 5 if t["ref"] else 1} for t in ts]) for ts in BY4]
    for seq in day_paths("H2", n, length=LEN, seed=SEED_FUND):
        f0 = RL.Rapid(U.UP25, F, {}, ("cushion", 500.0))
        f1 = Funded({**R("r25", "Z"), "lit_funded": U.UP25, "no_stuck": True}, "Z")
        for si in seq:
            e0, x0, _ = f0.step(BYn[si])
            e1, x1 = f1.step(Df[si])
            if (e0 or None) != (e1 or None) or abs((x0 or 0.0) - x1) > 0.02:
                bad += 1
                break
            if e0 == "lost":
                break
    res["c_funded_r25"] = bad
    # e: Rapid EOD 25K eval (30% best day + 4 days + the fleet guard), Zlarior alone, rapid25's sizing config
    ec = A4.ecfg(E, {"dll_off": True})               # = tools/money/rapid25.acct("25k") without its bar-loading streams
    ec["two_week"]["acct"]["dll"] = ec["_dll"] = 500.0
    sp = {"ecfg": ec, "E": E}
    bad = 0
    De = combo_days("Z")
    for seq in day_paths("H2", n, length=60):
        a, b = RL.Ev(sp["ecfg"], sp["E"], {}, "guard"), Eval({**R("r25", "Z"), "lit_eval": sp["ecfg"]}, "Z")
        for si in seq:
            ra, pa = a.step([{**t, "strat": "LIT"} for t in BY4[si]])
            rb, pb = b.step(De[si])
            if ra != rb or abs(pa - pb) > 0.02:
                bad += 1
                break
            if ra:
                break
    res["e_eval_r25"] = bad
    # d
    from engine import account_b as EAB
    pl = plan("b25")
    st = {"profit": 300.0, "cum": 0.0, "room": 900.0, "session": 3, "n_today": 0, "wk_pnl": 0.0, "days_traded": 2}
    T = [t for ts in trades() for t in ts if t["s"] == "A"][:300]
    q0 = [EAB.qty(pl["a_spec"], t["sze"], dict(st))["qty"] for t in T]
    _patch_account_b()
    q1 = [EAB.qty(pl["a_spec"], t["sze"], dict(st))["qty"] for t in T]
    res["d_atlas_cache"] = sum(1 for a, b in zip(q0, q1) if a != b)
    log(json.dumps(res))
    return res


# ================================================================================================ honesty checks (diagnostics)
HONEST_YEARS = [R("b50", "Z"), R("b50", "Z+A"), R("b50", "Z+A+B"), R("b50", "Z", "Z+A"), R("b25", "Z"), R("b25", "A"),
                R("b25", "Z+A"), R("b25", "Z+A+B"), R("r25", "Z+A", sizing="lanes"), R("r25", "Z+A+B", sizing="lanes")]
HONEST_ZERO = [{**R("b50", "Z"), "zero": ("Z",)}, {**R("b50", "Z+A"), "zero": ("A",)}, {**R("b50", "Z+A"), "zero": ("Z", "A")},
               {**R("b50", "Z+A+B"), "zero": ("A", "B")}, {**R("b50", "Z", "Z+A"), "zero": ("A",)},
               {**R("r25", "Z+A+B", sizing="lanes"), "zero": ("B",)}]


def honesty(n=N_PATHS, workers=3, log=print):
    """Not part of the verdict (that rule was fixed first): (1) the same rows inside each year of 2021-25, (2) a placebo with
    a bot's edge taken to zero (same timing, stops, variance): if a combo still "wins" with a zero-edge partner, the gain is
    the prop firm's capped downside (more variance = more lottery tickets), not the partner's edge."""
    trades()
    _patch_account_b()
    jobs = [(r, n, tuple(YEARS)) for r in HONEST_YEARS] + [(r, n) for r in HONEST_ZERO]
    res = {}
    import multiprocessing as mp
    with mp.get_context("fork").Pool(workers) as pool:
        for k, o, sec in pool.imap_unordered(_job, jobs):
            res[k] = {sp: {**{kk: vv for kk, vv in x.items() if not kk.startswith("_")}, "_net": x["_net"]} for sp, x in o.items()}
            log(f"{k} {sec:.0f}s")
    out = {"years": {}, "zero": {}}
    for r in HONEST_YEARS:
        k = row_key(r)
        out["years"][k] = {sp: res[k][sp]["slot"]["net_m"] for sp in YEARS}
        base = row_key(R(r["acct"], "Z"))
        if k != base and base in res:
            out["years"][k]["gap_vs_Z"] = {sp: [round(x, 1) for x in paired(res[k][sp]["_net"], res[base][sp]["_net"])] for sp in YEARS}
    for r in HONEST_ZERO:
        k = row_key(r)
        out["zero"][k] = {sp: {"net_m": res[k][sp]["slot"]["net_m"], "p_neg": res[k][sp]["slot"]["p_neg"],
                               "eval_f60": res[k][sp]["slot"]["eval"]["f60"], "pay30": res[k][sp]["funded"]["pay30"]} for sp in SPANS}
    return out


# ================================================================================================ tables for the write-up
def _m(x):
    return "-" if x is None else (f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}")


def label(r):
    nm = r["eval"] if r["eval"] == r["funded"] else f"{r['eval']} eval, {r['funded']} funded"
    if "+" in r["eval"] or "+" in r["funded"]:
        nm += f" ({r['sizing']})"
    if r["rule"] == "adds":
        nm += " adds"
    if r["ticks"]:
        nm += " +1 tick"
    return nm


def tables(o) -> str:
    L = []
    rows = o["rows"]
    L.append("### A. The trades themselves (real days in order, $250 a trade, one position first-in, costs in)\n")
    L.append("| Combo | trades/wk H1 / H2 / 21-25 | win % | PF | net $ | $/month | max DD |")
    L.append("|---|---|---|---|---|---|---|")
    for c in COMBOS + ("Z+A+P", "Z+A+B+P"):
        p = o["plain"].get(f"{c}|first|t0")
        if not p:
            continue
        L.append(f"| {c} | " + " / ".join(f"{p[s]['tpw']}" for s in SPANS) + " | " + " / ".join(f"{p[s]['win']}" for s in SPANS)
                 + " | " + " / ".join(f"{p[s]['pf']}" for s in SPANS) + " | " + " / ".join(_m(p[s]["net"]) for s in SPANS)
                 + " | " + " / ".join(_m(p[s]["per_month"]) for s in SPANS)
                 + " | " + " / ".join(_m(p[s]["max_dd"]) for s in SPANS) + " |")
    for a in ACCTS:
        L.append(f"\n### {PLANS[a]['label']} (${PLANS[a]['price']:.2f})\n")
        L.append("| Row | $/month after fees, H1 / H2 / 21-25 (10-90% of paths) | lose money in 6 mo | eval pass in 60 / median days (25-75%) / fail | funded: 1st payout <= 30 / 60 days, lost or stuck |")
        L.append("|---|---|---|---|---|")
        for k, r in rows.items():
            if r["acct"] != a or r["group"] != "main":
                continue
            cur = " **(today)**" if k in o["current"][a] else ""
            money = " / ".join(f"{_m(r[s]['slot']['net_m'])} ({_m(r[s]['slot']['p10_m'])}..{_m(r[s]['slot']['p90_m'])})" for s in SPANS)
            neg = " / ".join(f"{r[s]['slot']['p_neg']}%" for s in SPANS)
            ev = " / ".join(f"{r[s]['slot']['eval']['p60']}%, {r[s]['slot']['eval']['pass_med'] or '-'}"
                            f" ({'-'.join(str(int(x)) for x in (r[s]['slot']['eval']['pass_q'] or [])) or '-'}), {r[s]['slot']['eval']['f60']}%" for s in SPANS)
            fu = " / ".join(f"{r[s]['funded']['pay30']}/{r[s]['funded']['pay60']}%, {r[s]['funded']['lost_or_stuck']}%" for s in SPANS)
            L.append(f"| {label(r)}{cur} | {money} | {neg} | {ev} | {fu} |")
    L.append("\n### Sensitivities ($/month after fees, H1 / H2 / 21-25)\n")
    L.append("| Account | Row | main | +1 tick | same-side adds |")
    L.append("|---|---|---|---|---|")
    for k, r in rows.items():
        if r["group"] != "main":
            continue
        tk = rows.get(row_key({**r, "ticks": 1}))
        ad = rows.get(row_key({**r, "rule": "adds"}))
        f = lambda x: " / ".join(_m(x[s]["slot"]["net_m"]) for s in SPANS) if x else "-"  # noqa: E731
        L.append(f"| {PLANS[r['acct']]['label']} | {label(r)} | {f(r)} | {f(tk)} | {f(ad)} |")
    L.append("\n### Zlarior eval, combo once funded; post-close lead added ($/month after fees H1 / H2 / 21-25; funded 1st payout <= 30 days)\n")
    L.append("| Account | Row | $/month | funded pay <= 30 d | eval fail in 60 |")
    L.append("|---|---|---|---|---|")
    for k, r in rows.items():
        if r["group"] not in ("funded_only", "pcm"):
            continue
        L.append(f"| {PLANS[r['acct']]['label']} | {label(r)} | " + " / ".join(_m(r[s]["slot"]["net_m"]) for s in SPANS) + " | "
                 + " / ".join(f"{r[s]['funded']['pay30']}%" for s in SPANS) + " | " + " / ".join(f"{r[s]['slot']['eval']['f60']}%" for s in SPANS) + " |")
    L.append("\n### Verdict (pre-registered: above today's setup by > 2 SE in all three periods, 6-month loss chance not +5 pts, still above at +1 tick)\n")
    L.append("| Account | Row | gap vs today $/month H1 / H2 / 21-25 (2 SE) | beats today? |")
    L.append("|---|---|---|---|")
    for k, v in o["verdict"].items():
        r = rows[k]
        gaps = " / ".join(", ".join(f"{c['gap_m']:+,} ({2 * c['se']:,.0f})" for c in v["checks"][s]) for s in SPANS)
        L.append(f"| {PLANS[r['acct']]['label']} | {label(r)} | {gaps} | {'YES' if v['beats_today'] else 'no'} |")
    return "\n".join(L)


# ================================================================================================ FINAL rules (night-comboplus)
# Pre-registered: research/lab/combo_final_design_2026-11-19.md (committed before any variant result). Builder 50K only,
# Zlarior + ATLAS, MFFU's move to live after the 5th payout in every row ("live"), day AND week bootstraps.
FINAL_OUT = os.path.join(ROOT, "research", "lab", "combo_final.json")
FINAL_CFG = os.path.join(ROOT, "research", "lab", "combo_50k.json")
FINAL_DESIGN = "research/lab/combo_final_design_2026-11-19.md"
SEED_WEEK, SEED_WEEK_F, SEED_HIST = 202, 203, 606
N_HIST, N_HIST_PATHS = 200, 500
F_SPANS = ("H1", "H2", "REF", "Y2022")
VARIANTS = [   # id, eval combo, funded combo, conflict, ATLAS share {eval, funded}, eval room guard, eval day cap, plain reason
    ("base", "Z+A", "Z+A", "first", 1.0, 1.0, None, None, "the study's proposal: first in keeps the account"),
    ("zprio", "Z+A", "Z+A", "zprio", 1.0, 1.0, None, None, "Zlarior entering the other way closes ATLAS (today's HEDGE rule)"),
    ("zfull", "Z+A", "Z+A", "zfull", 1.0, 1.0, None, None, "any Zlarior entry closes an open ATLAS trade"),
    ("a60", "Z+A", "Z+A", "first", 0.6, 0.6, None, None, "ATLAS at 60% of its own size"),
    ("a40", "Z+A", "Z+A", "first", 0.4, 0.4, None, None, "ATLAS at 40% of its own size"),
    ("a_eval_off", "Z", "Z+A", "first", 0.0, 1.0, None, None, "ATLAS sits out the eval, full size once funded"),
    ("a50_eval", "Z+A", "Z+A", "first", 0.5, 1.0, None, None, "ATLAS at 50% in the eval, 100% once funded"),
    ("room1500", "Z+A", "Z+A", "first", 1.0, 1.0, 1500.0, None, "in the eval ATLAS trades only with >= $1,500 of room"),
    ("daycap500", "Z+A", "Z+A", "first", 1.0, 1.0, None, 500.0, "in the eval no new entry after a -$500 day"),
    ("a60_room1500", "Z+A", "Z+A", "first", 0.6, 0.6, 1500.0, None, "ATLAS 60% + the $1,500 room guard"),
    ("room1500_daycap500", "Z+A", "Z+A", "first", 1.0, 1.0, 1500.0, 500.0, "the $1,500 room guard + the -$500 day cap"),
    ("a_eval_off_a60", "Z", "Z+A", "first", 0.0, 0.6, None, None, "ATLAS sits out the eval, 60% once funded"),
]
VIDS = [v[0] for v in VARIANTS]
F_TESTS = {   # test -> (periods, bootstrap, row overrides, with funded-only stats)
    "day": (F_SPANS, "day", {}, True),
    "week": (F_SPANS, "week", {}, True),
    "day_t1": (SPANS, "day", {"ticks": 1}, False),
    "week_t1": (SPANS, "week", {"ticks": 1}, False),
    "day_drop5": (SPANS, "day", {"drop5": True}, False),
    "day_stop": (SPANS, "day", {"live": "stop"}, False),
    "day_rebuy": (SPANS, "day", {"live": "rebuy"}, False),        # parity with the study (base and Zlarior alone only)
}


def frow(vid, **kw):
    """a final-study row: Builder 50K, own sizes, MFFU live move ("live") unless overridden."""
    if vid == "Z":
        r = {**R("b50", "Z"), "live": "live", "vid": "Z"}
    else:
        v = next(x for x in VARIANTS if x[0] == vid)
        r = {**R("b50", v[1], v[2]), "live": "live", "vid": vid, "conflict": v[3], "a_f": {"eval": v[4], "funded": v[5]},
             "a_room_min": v[6], "day_cap": v[7]}
    r.update(kw)
    return r


def week_blocks(span):
    """the period's sessions as calendar weeks (Mon-Fri) -> [[session index, ...], ...]"""
    S = sessions()
    a, z = span_ix(span)
    wk = collections.OrderedDict()
    for i in range(a, z):
        y, w, _ = dt.date.fromisoformat(S[i]).isocalendar()
        wk.setdefault((y, w), []).append(i)
    return list(wk.values())


def week_paths(span, n, seed, length=LEN, blocks=None):
    """whole calendar weeks drawn with replacement and laid end to end (a bad week stays a bad week), cut at `length`."""
    B = blocks or week_blocks(span)
    rng = np.random.default_rng(seed)
    out = np.empty((n, length), dtype=np.int64)
    for p in range(n):
        seq = []
        while len(seq) < length:
            seq += B[int(rng.integers(0, len(B)))]
        out[p] = seq[:length]
    return out


def pool_paths(pool, n, seed, length=LEN):
    pool = np.asarray(pool)
    return pool[np.random.default_rng(seed).integers(0, len(pool), size=(n, length))]


def best_atlas_days(span, k=5):
    """ATLAS's k best days of the period by its stored R (the same days for every row)."""
    a, z = span_ix(span)
    by = collections.defaultdict(float)
    for i in range(a, z):
        for t in trades()[i]:
            if t["s"] == "A" and t["risk"]:
                by[t["day"]] += t["pts"] / t["risk"]
    return [d for d, _ in sorted(by.items(), key=lambda x: -x[1])[:k]]


def f_paths(boot, span, n, funded=False):
    if boot == "day":
        return day_paths(span, n, seed=SEED_FUND if funded else SEED_SLOT)
    return week_paths(span, n, seed=SEED_WEEK_F if funded else SEED_WEEK)


def _final_job(args):
    vid, test, n = args
    _patch_account_b()
    spans, boot, ov, with_f = F_TESTS[test]
    t0 = time.time()
    o = {}
    for sp in spans:
        kw = {k: v for k, v in ov.items() if k != "drop5"}
        if ov.get("drop5"):
            kw["drop"] = tuple(best_atlas_days(sp))
        r = frow(vid, **kw)
        sl = run_slot(r, f_paths(boot, sp, n))
        x = {"slot": slot_stats(sl), "_net": np.array([q[0] for q in sl]) / MONTHS,
             "live_n": round(float(np.mean([q[11] for q in sl])), 2), "owner_live_m": round(float(np.mean([q[12] for q in sl])) / MONTHS),
             "grads": round(float(np.mean([q[13] for q in sl])), 2)}
        if with_f:
            x["funded"] = funded_stats(run_funded(r, f_paths(boot, sp, n, funded=True)))
        o[sp] = x
    return vid, test, o, round(time.time() - t0, 1)


def _hist_job(args):
    """one resampled H2 history: its 16 weeks redrawn (seeded), N day paths from that pool, every row on the same paths."""
    b, pool, n = args
    _patch_account_b()
    P = pool_paths(pool, n, seed=1000 + b)
    return b, {vid: float(np.mean([q[0] for q in run_slot(frow(vid), P)]) / MONTHS) for vid in ["Z"] + VIDS}


def hist_pools(span="H2", B=N_HIST):
    W = week_blocks(span)
    rng = np.random.default_rng(SEED_HIST)
    return [[i for j in rng.integers(0, len(W), size=len(W)) for i in W[int(j)]] for _ in range(B)]


def final_constraints(res, hist):
    """the pre-registered pick (design file section 3)."""
    out = {}
    for vid in VIDS:
        c, info = {}, {}
        g = {}
        for test in ("day", "week", "day_t1", "week_t1", "day_drop5", "day_stop"):
            base = "day" if test == "day_drop5" else test
            for sp in F_TESTS[test][0]:
                m, se = paired(res[vid][test][sp]["_net"], res["Z"][base][sp]["_net"])
                g[(test, sp)] = (round(m), round(se, 1))
        info["gaps"] = {f"{t}|{sp}": v for (t, sp), v in g.items()}
        c["C1"] = all(g[(b, sp)][0] > 2 * g[(b, sp)][1] for b in ("day", "week") for sp in ("H1", "H2"))
        c["C2"] = all(g[(b, "REF")][0] >= -50 for b in ("day", "week"))
        f10 = {(b, sp): res[vid][b][sp]["slot"]["eval"]["f10"] for b in ("day", "week") for sp in ("H1", "H2")}
        c["C3"] = all(v <= 5.0 for v in f10.values())
        c["C4"] = all(g[(b, sp)][0] > 0 for b in ("day_t1", "week_t1") for sp in ("H1", "H2"))
        h = np.array([x[vid] - x["Z"] for x in hist])
        share = float((h <= 0).mean())
        c["C5"] = share <= 0.07
        info["f10"] = {f"{b}|{sp}": v for (b, sp), v in f10.items()}
        info["hist"] = {"share_le0": round(share, 3), "p10": round(float(np.percentile(h, 10))), "p50": round(float(np.median(h))),
                        "p90": round(float(np.percentile(h, 90))), "n": len(h)}
        out[vid] = {"pass": c, "all4": all(c[k] for k in ("C1", "C2", "C3", "C4")), "all5": all(c.values()),
                    "h2_week_m": res[vid]["week"]["H2"]["slot"]["net_m"], **info}
    A = [v for v in VIDS if out[v]["all5"]]
    Bt = [v for v in VIDS if out[v]["all4"]]
    if A:
        tier, win = "A", max(A, key=lambda v: out[v]["h2_week_m"])
    elif Bt:
        tier, win = "B", max(Bt, key=lambda v: out[v]["h2_week_m"])
    else:
        tier, win = "C", "base"
    return {"rows": out, "tier": tier, "winner": win, "tier_A": A, "tier_B": Bt}


def final(n=N_PATHS, workers=3, n_hist=N_HIST, n_hist_paths=N_HIST_PATHS, log=print):
    trades()
    atlas_paths()
    _patch_account_b()
    jobs = []
    for vid in ["Z"] + VIDS:
        for test in F_TESTS:
            if test == "day_rebuy" and vid not in ("Z", "base"):
                continue
            if test == "day_drop5" and vid == "Z":
                continue
            jobs.append((vid, test, n))
    pools = hist_pools("H2", n_hist)
    hjobs = [(b, pools[b], n_hist_paths) for b in range(n_hist)]
    log(f"{len(jobs)} row-tests ({len(VIDS)} variants + Zlarior alone), {n} paths; {n_hist} H2 histories x {n_hist_paths} paths")
    res = collections.defaultdict(dict)
    hist = []
    t0 = time.time()
    import multiprocessing as mp
    with mp.get_context("fork").Pool(workers) as pool:
        for i, (vid, test, o, sec) in enumerate(pool.imap_unordered(_final_job, jobs)):
            res[vid][test] = o
            log(f"[{i + 1}/{len(jobs)}] {vid} {test} {sec:.0f}s ({time.time() - t0:.0f}s)")
        for i, (b, x) in enumerate(pool.imap_unordered(_hist_job, hjobs)):
            hist.append(x)
            if i % 20 == 19:
                log(f"[hist {i + 1}/{len(hjobs)}] ({time.time() - t0:.0f}s)")
    res["Z"]["day_drop5"] = res["Z"]["day"]
    pick = final_constraints(res, hist)
    cuts = {}
    for vid in ("zprio", "zfull"):                       # how many ATLAS trades a conflict rule closes on the real days
        cuts[vid] = {}
        for sp in SPANS:
            a, z = span_ix(sp)
            b = Book(cell_of(frow(vid)), "funded", "Z+A")
            b.bal = 1e6
            n_c = 0
            for i in range(a, z):
                b.cuts = 0
                b.trade_day(combo_days("Z+A")[i])
                n_c += b.cuts
            cuts[vid][sp] = n_c
    strip = lambda o: {sp: {k: v for k, v in x.items() if not k.startswith("_")} for sp, x in o.items()}  # noqa: E731
    out = {"date": DATE, "design": FINAL_DESIGN, "n": n, "n_hist": n_hist, "n_hist_paths": n_hist_paths,
           "variants": [{"id": v[0], "eval": v[1], "funded": v[2], "conflict": v[3], "a_f": {"eval": v[4], "funded": v[5]},
                         "a_room_min": v[6], "day_cap": v[7], "why": v[8]} for v in VARIANTS],
           "results": {vid: {test: strip(o) for test, o in T.items()} for vid, T in res.items()},
           "hist_raw": hist, "pick": pick, "cuts": cuts, "best_atlas_days": {sp: best_atlas_days(sp) for sp in SPANS},
           "live_rules": LIVE, "secs": round(time.time() - t0)}
    return out


def final_config(o) -> dict:
    """research/lab/combo_50k.json: the rules the live build reads."""
    w = o["pick"]["winner"]
    v = next(x for x in o["variants"] if x["id"] == w)
    R_ = o["results"]
    ev = {}
    for sp in ("H1", "H2", "REF", "Y2022"):
        z, x = R_["Z"]["week"][sp]["slot"], R_[w]["week"][sp]["slot"]
        zd, xd = R_["Z"]["day"][sp]["slot"], R_[w]["day"][sp]["slot"]
        ev[sp] = {"usd_month_week": x["net_m"], "usd_month_day": xd["net_m"], "zlarior_alone_week": z["net_m"],
                  "zlarior_alone_day": zd["net_m"], "range_10_90_week": [x["p10_m"], x["p90_m"]],
                  "eval_fail_2wk_week": x["eval"]["f10"], "eval_fail_60_week": x["eval"]["f60"],
                  "eval_pass_median_days": x["eval"]["pass_med"],
                  "funded_pay30_week": R_[w]["week"][sp]["funded"]["pay30"], "funded_pay60_week": R_[w]["week"][sp]["funded"]["pay60"]}
    P = o["pick"]["rows"][w]
    return {"version": 1, "account": "builder50k", "bots": ["lit", "atlas"], "conflict": v["conflict"],
            "atlas_size_factor": v["a_f"]["funded"] if v["a_f"]["eval"] == v["a_f"]["funded"] else None,
            "atlas_size_factor_by_stage": v["a_f"],
            "guards": {"atlas_in_eval": v["a_f"]["eval"] > 0, "atlas_eval_min_room_usd": v["a_room_min"],
                       "eval_day_stop_usd": v["day_cap"], "one_position": True, "soft_day_usd_both_bots": 1000.0,
                       "max_micros": 40, "flat_by": "16:10 ET"},
            "sizes": {"lit_eval": "live_model.json lit_sizing two_week (room_f 0.4, kept to session 80)",
                      "lit_funded": "engine/multi_account builder 50K funded preset",
                      "atlas": "engine/account_b plan builder50k (need size in the eval, funded_qty once funded), x atlas_size_factor"},
            "variant": w, "pick_tier": o["pick"]["tier"],
            "evidence": {"source": "research/writeups/one-account-combo-final-2026-11-19.md", "results": "research/lab/combo_final.json",
                         "design": FINAL_DESIGN, "n_paths": o["n"], "periods": ev,
                         "h2_resampled_histories_gap_le0": P["hist"]["share_le0"], "constraints": P["pass"],
                         "variants_tried": len(o["variants"]), "date": DATE, "paper_only": True}}


def final_tables(o) -> str:
    R_, pk = o["results"], o["pick"]
    L = []
    W = {"H1": "Jan-Jun", "H2": "Jul-Oct", "REF": "2021-25", "Y2022": "2022"}

    def money(vid, test, sp):
        return R_[vid][test][sp]["slot"]["net_m"]
    L.append("### Money ($ a month after fees, MFFU live move in; week-block / day-block bootstrap; gap vs Zlarior alone)\n")
    L.append("| Row | " + " | ".join(W[s] for s in F_SPANS) + " | C1-C5 |")
    L.append("|---|" + "---|" * (len(F_SPANS) + 1))
    for vid in ["Z"] + VIDS:
        cells = []
        for sp in F_SPANS:
            wk, dy = money(vid, "week", sp), money(vid, "day", sp)
            if vid == "Z":
                cells.append(f"{_m(wk)} / {_m(dy)}")
            else:
                gw = pk["rows"][vid]["gaps"][f"week|{sp}"][0]
                cells.append(f"{_m(wk)} / {_m(dy)} ({gw:+,})")
        cc = "today" if vid == "Z" else "".join("Y" if pk["rows"][vid]["pass"][k] else "n" for k in ("C1", "C2", "C3", "C4", "C5"))
        L.append(f"| {vid} | " + " | ".join(cells) + f" | {cc} |")
    L.append("\n### Safety and speed (week-block; day-block in brackets)\n")
    L.append("| Row | eval fail in 2 weeks H1 / H2 / 21-25 | eval fail in 60 H1 / H2 | eval pass median days H1 / H2 | funded 1st payout <= 30 / 60 d H2 | 6 months lose money H2 |")
    L.append("|---|---|---|---|---|---|")
    for vid in ["Z"] + VIDS:
        w_, d_ = R_[vid]["week"], R_[vid]["day"]
        L.append(f"| {vid} | " + " / ".join(f"{w_[s]['slot']['eval']['f10']}% ({d_[s]['slot']['eval']['f10']}%)" for s in SPANS)
                 + " | " + " / ".join(f"{w_[s]['slot']['eval']['f60']}%" for s in ("H1", "H2"))
                 + " | " + " / ".join(f"{w_[s]['slot']['eval']['pass_med']}" for s in ("H1", "H2"))
                 + f" | {w_['H2']['funded']['pay30']}% / {w_['H2']['funded']['pay60']}% | {w_['H2']['slot']['p_neg']}% |")
    L.append("\n### Robustness (gap vs Zlarior alone, $ a month; H1 / H2 / 21-25)\n")
    L.append("| Row | +1 tick (week) | ATLAS's 5 best days removed (day) | live worth $0 (stop at payout 5, day) | old model: new eval after payout 5 (day) | H2 histories: gap <= $0 / 10% / median / 90% |")
    L.append("|---|---|---|---|---|---|")
    for vid in VIDS:
        g = pk["rows"][vid]["gaps"]
        f = lambda t: " / ".join(f"{g[f'{t}|{s}'][0]:+,}" for s in SPANS)  # noqa: E731
        rb = "-"
        if "day_rebuy" in R_[vid]:
            rb = " / ".join(f"{R_[vid]['day_rebuy'][s]['slot']['net_m'] - R_['Z']['day_rebuy'][s]['slot']['net_m']:+,}" for s in SPANS)
        h = pk["rows"][vid]["hist"]
        L.append(f"| {vid} | {f('week_t1')} | {f('day_drop5')} | {f('day_stop')} | {rb} | {100 * h['share_le0']:.1f}% / {h['p10']:+,} / {h['p50']:+,} / {h['p90']:+,} |")
    L.append(f"\nPick: tier {pk['tier']}, winner **{pk['winner']}** (tier A = all of C1-C5: {pk['tier_A'] or 'none'}; C1-C4: {pk['tier_B'] or 'none'}).")
    return "\n".join(L)


# ================================================================================================ main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build-blitz", "build", "check", "study", "table", "honesty", "build-paths", "final", "final-table"])
    ap.add_argument("--tf", type=int, default=1)
    ap.add_argument("--n", type=int, default=N_PATHS)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--group", default=None, help="study only rows of this group (main, tick, adds, funded_only, pcm)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    if a.cmd == "build-blitz":
        print("->", build_blitz(a.tf))
        return 0
    if a.cmd == "build-paths":
        print(build_paths())
        return 0
    if a.cmd == "build":
        o = build()
        print("trades", o["count"], "->", os.path.relpath(TRADES, ROOT))
        return 0
    if a.cmd == "honesty":
        o = honesty(a.n, a.workers)
        p = os.path.join(ROOT, "research", "lab", "combo_account_honesty.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(o, fh, indent=1)
        print(json.dumps(o, indent=1))
        return 0
    if a.cmd == "table":
        print(tables(json.load(open(a.out, encoding="utf-8"))))
        return 0
    if a.cmd == "final":
        o = final(a.n, a.workers)
        with open(FINAL_OUT, "w", encoding="utf-8") as fh:
            json.dump(o, fh, indent=1)
        cfg = final_config(o)
        with open(FINAL_CFG, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, indent=1)
        print(final_tables(o))
        print("wrote", os.path.relpath(FINAL_OUT, ROOT), os.path.relpath(FINAL_CFG, ROOT), f"{o['secs']}s")
        return 0
    if a.cmd == "final-table":
        print(final_tables(json.load(open(FINAL_OUT, encoding="utf-8"))))
        return 0
    if a.cmd == "check":
        r = check()
        return 0 if not any(r.values()) else 1
    t0 = time.time()
    out = study(a.n, a.workers, (lambda r: r["group"] == a.group) if a.group else None)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("wrote", os.path.relpath(a.out, ROOT), f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
