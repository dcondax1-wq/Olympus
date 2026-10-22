"""LIT + the second strategies (2026-10-22): what is the best way to combine them, in $ and MFFU eval odds?

Inputs (all stored, nothing re-tuned here):
  LIT       the live LIT (live_model.json "lit": t_check + be_off on, scale_in off) = run lit_live; engine/lit.py run_x via
            tools/lit_final.run, turned into eval units by tools/lit_adopt_combo.units (2026: 1m; 2021-25: 5m, no 1m bars)
  Asia      the Asia-slot trades (entries 18:00-02:00 ET) of variant asiaslotn_rr3_x1.0 = run lit_more_ent_asia_slot_rr3
            (tools/lit_more_entries.py), as LIT units (LIT sizing, LIT priority)
  EMA / MD / SR   research/second/ema_best.json, md_best.json, sr_best.json (every trade 2021-11 .. 2026-10, common format);
            per-micro points = (exit - entry) x dir (slippage in the stored exit), worst open points from the 5m bars between
            the entry bar and the exit bar (capped at the stop + 1 tick), $1.90 a micro

Part 1, ONE MFFU Builder 50K eval with LIT (tools/lit_adv_manage.run_eval generalised): every session's candidate trades in
entry order (LIT first on a tie); one position at a time (a trade that signals while another is open is skipped: a LIT trade
lost that way is counted), max 2 trades a day with one slot always kept for LIT's own day trade (a second-strategy trade
needs a free slot after that reservation), the account's $1,000 soft daily loss over all trades of the day (cum <= -1,000
stops the day; a trade that would cross it is cut there, as run_eval). LIT (and Asia) size = the live lit_sizing (two_week
for 10 sessions, then safe_eval, no reset). Second-strategy sizes:
  usd300 / usd500        fixed $ risk: int(usd / (stop x $2)), max 40
  +safe                  capped at 0.6 x room / (stop x $2), min 1 micro (room = balance incl. today's closed P&L - floor)
  +dll                   capped so a stop-out (2 ticks slippage, $1.90) fits in what is left of today's $1,000 soft loss
  need0.25 / 0.5 / 1.0   that share of LIT's own two_week "need" micros (engine/sizing.lit_qty on the trade's stop and target)
Scoring like tools/lit_adv_manage: a fresh eval started on every session of a span, 20 sessions, sessions inside the span;
2-week / 1-month pass and fail % over the starts that can see 10 / 20 sessions; median sessions of a pass; $ = the
back-to-back eval path (owner's no-reset policy). Spans: 2026 H1 (pick), H2 (check), 2025 and 2021-24 (reference; LIT on
5m there).

Part 2, SEPARATE accounts: each second strategy alone on its own Builder 50K ($91.80): eval odds, eventual pass within 60
sessions, then the MFFU sim-funded account (research/lit/mffu_rules.json via engine/sizing.FD_50K and tools/lit_funded
rules: EOD trailing $2,000 to +$100, buffer $2,100, payouts $500-$2,000 80/20, 2 traded days a cycle, 50% consistency,
5 payouts) for 126 sessions: $ to the trader per funded account and per eval bought.

    python -X utf8 tools/second_mix.py units     # build the unit caches (engine runs, a few minutes)
    python -X utf8 tools/second_mix.py check     # LIT alone == run lit_adopt_t15_be_off_eval (57.1/5.9, 52.2/0.0)
    python -X utf8 tools/second_mix.py grid      # every combination -> research/second/mix.json
    python -X utf8 tools/second_mix.py separate  # part 2 -> research/second/mix.json ("separate")
    python -X utf8 tools/second_mix.py save      # rl.save the top runs mix_*
Paper only. Edits no engine file, no live_model*.json.
"""
from __future__ import annotations

import collections
import datetime as dt
import itertools
import json
import os
import pickle
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402

OUT = os.path.join(ROOT, "research", "second", "mix.json")
CACHE = os.path.join(ROOT, "research", "runs", "_cache", "second_mix_units.pkl")
ET = ZoneInfo("America/New_York")
PV, ECOMM, SLIP = 2.0, SZ.TW_COMM, 0.25
TGT, MLL, DLL, LOCK = 3000.0, 2000.0, 1000.0, 100.0
PRICE = 91.80
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2025": ("2025-01-01", "2025-12-31"),
         "2021-24": ("2021-01-01", "2024-12-31")}
SECOND = {"EMA": "ema_best.json", "MD": "md_best.json", "SR": "sr_best.json"}
ASIA_V = "asiaslotn_rr3_x1.0"
_LM = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
CFG = {**{k: _LM[k] for k in ("two_week", "safe_cap", "eval_ref_stop", "fast_ref_stop")}, "mode": "two_week",
       "two_week_until": _LM.get("two_week_until", 10), "after_mode": _LM.get("after_mode", "safe_eval")}


# ================================================================================================ units
def et_mod(ts):
    x = dt.datetime.fromtimestamp(int(ts), ET)
    return x.hour * 60 + x.minute


def lit_units(T):
    """tools/lit_adopt_combo.units without its 2026-only filter (pre-2026 trades are 5m, w1 from the 5m bars)."""
    from tools import lit_adopt_combo as AC
    from tools import lit_final as F
    M, _ = F.market(AC.LIVE["ref"], AC.LIVE.get("extra_boxes") or [])
    B1, B5 = F.bars(M, "1m"), F.bars(M, "5m")
    out = []
    for t in T:
        d = int(t["dir"])
        B = B1 if t.get("tf") == 1 else B5
        e = float(t["entry_px"]) * d
        pts = (t["pnl"] + lit.COMM * t["qty"]) / (lit.PV * t["qty"])
        k0 = int(np.searchsorted(B.t, int(t["entry_t"])))
        kx = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
        if t["exit"] == "CUT_T15":
            kx -= 1
        lo = B.l if d == 1 else -B.h
        w1 = min(0.0, float(lo[k0:kx + 1].min()) - e) if kx >= k0 else 0.0
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": d, "exit": t["exit"],
                    "risk": float(t["risk_pts"]), "tgt": round(d * (float(t["target_px"]) - float(t["entry_px"])), 4),
                    "pts": round(pts, 4), "w1": round(w1, 4), "legs": [(1.0, round(pts, 4))], "on1": t.get("tf") == 1})
    return out


def second_units(name):
    """A second strategy's stored trades -> units (risk, tgt, pts per micro, w1 worst open pts from the 5m bars)."""
    from tools import lit_final as F
    M, _ = F.market("cisd", [])
    B5, B1 = F.bars(M, "5m"), F.bars(M, "1m")
    d = json.load(open(os.path.join(ROOT, "research", "second", SECOND[name]), encoding="utf-8"))
    out = []
    for t in d["trades"]:
        dr = int(t["dir"])
        e, s, x = float(t["entry"]), float(t["stop"]), float(t["exit"])
        risk = abs(e - s)
        if risk <= 0:
            continue
        pts = (x - e) * dr
        tgt = abs(float(t["target"]) - e) if t.get("target") is not None else 3.0 * risk
        B = B1 if int(t["entry_t"]) >= int(B1.t[0]) + 86400 else B5
        k0 = int(np.searchsorted(B.t, int(t["entry_t"]), side="right"))     # the bar after the entry bar
        kx = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
        lo = B.l if dr == 1 else -B.h
        w = float(lo[k0:kx].min()) - e * dr if kx > k0 else 0.0
        w1 = max(-(risk + 0.25), min(0.0, w, pts))
        # path for a LIT pre-emption: bar open times, open pts (dir space, from the entry), worst pts before that bar
        op = (B.o[k0:kx + 1] * dr - e * dr) if kx >= k0 else np.zeros(0)
        lw = np.minimum.accumulate(np.r_[0.0, lo[k0:kx] - e * dr]) if kx >= k0 else np.zeros(0)
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": dr, "exit": t["exit_kind"],
                    "risk": round(risk, 4), "tgt": round(tgt, 4), "pts": round(pts, 4), "w1": round(w1, 4), "src": name,
                    "pt": B.t[k0:kx + 1].astype(np.int64), "po": np.round(op, 2), "pw": np.maximum(np.round(lw, 2), -(risk + 0.25))})
    return out


def build_units():
    from tools import lit_final as F
    from tools import lit_more_entries as ME
    from tools import lit_adopt_combo as AC
    T = F.run(AC.LIVE | {"t_check": AC.T15, "be_off": AC.BE_OFF})
    U = {"LIT": [u | {"src": "LIT"} for u in lit_units(T)]}
    print("LIT", len(U["LIT"]), "units", flush=True)
    P = ME.variants()[ASIA_V]
    TA = ME.run(P)
    UA = lit_units(TA)
    U["_asia_all"] = UA
    U["Asia"] = [u | {"src": "Asia"} for u in UA if et_mod(u["entry_t"]) >= 1080 or et_mod(u["entry_t"]) < 120]
    print("Asia-slot run", len(UA), "units,", len(U["Asia"]), "Asia entries", flush=True)
    for nm in SECOND:
        U[nm] = second_units(nm)
        print(nm, len(U[nm]), "units", flush=True)
    U["sessions"] = F.SESS
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    pickle.dump(U, open(CACHE, "wb"))
    return U


_UC = {}


def units():
    if "u" not in _UC:
        _UC["u"] = pickle.load(open(CACHE, "rb")) if os.path.exists(CACHE) else build_units()
    return _UC["u"]


# ================================================================================================ sizing
LITLIKE = ("LIT", "Asia")


def lit_q(t, st, cfg=None):
    cfg = cfg or CFG
    m0 = lit.qty_for(t["risk"])
    return SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, cfg, room=st["room"], state=st,
                      learning=None)["qty"] if m0 else 0


def dll_cap(t, st):
    return int(max(0.0, DLL + st["cum"]) / ((t["risk"] + SZ.TW_DLL_SLIP) * PV + ECOMM))


def second_q(t, st, rule):
    """rule: "usd300" | "usd500" (+ "_safe", "_dll") | "need0.5" ..."""
    r = t["risk"]
    if rule.startswith("need"):
        q = lit_q(t, st)
        if q <= 0:
            return 0
        return max(1, int(q * float(rule[4:]) + 1e-9))
    base, *flags = rule.split("_")
    q = min(40, int(float(base[3:]) / (r * PV)))
    if "safe" in flags and q > 0:                           # min 1 micro, as the live safe_eval
        q = max(1, min(q, int(0.6 * max(0.0, st["room"]) / (r * PV))))
    if "dll" in flags:
        q = min(q, dll_cap(t, st))
    return max(0, q)


# ================================================================================================ one eval
def by_day(U):
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: (t["entry_t"], 0 if t["src"] in LITLIKE else 1)):
        by[t["day"]].append(t)
    return by


def cut_at(t, ts):
    """A second-strategy trade flattened at time ts (LIT pre-empts it): (pts per micro incl. 1 tick slippage, worst pts)."""
    k = int(np.searchsorted(t["pt"], ts))
    if k >= len(t["pt"]):
        return t["pts"], t["w1"]
    pts = min(float(t["po"][k]), 1e9) - SLIP
    w = min(0.0, float(t["pw"][k]), pts)
    return pts, w


def play_day(L, day, bal, floor, session, rule, pre=False, max_day=2, lost=None, litcfg=None, dll=DLL, reserve=True, extra=None):
    """One session of an account: the day's candidate trades L (entry order). Returns (cum, recs, failed). bal / floor: the
    account balance and trailing floor at the session start (profit space)."""
    cum, busy, n, lit_done, recs = 0.0, 0, 0, False, []
    for j, t in enumerate(L):
        if cum <= -dll:
            break
        litlike = t["src"] in LITLIKE
        if t["entry_t"] < busy or n >= max_day:
            if litlike and lost is not None:
                lost.append((day, t["src"]))
            continue
        if not litlike and n + (0 if (lit_done or not reserve) else 1) >= max_day:
            continue
        st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": session, "n_today": 0, **(extra or {})}
        q = (lit_q(t, st, litcfg) if litcfg else lit_q(t, st)) if litlike else second_q(t, st, rule)
        if q <= 0:
            continue
        pts, w1, ex, xt = t["pts"], t["w1"], t["exit"], t["exit_t"]
        if pre and not litlike:
            nxt = next((x for x in L[j + 1:] if x["src"] in LITLIKE and t["entry_t"] <= x["entry_t"] < t["exit_t"]), None)
            if nxt is not None:
                pts, w1 = cut_at(t, nxt["entry_t"]); ex, xt = "PRE", nxt["entry_t"]
        pnl = pts * PV * q - ECOMM * q
        low = min(0.0, w1 * PV * q - ECOMM * q, pnl)
        if cum + low <= -dll:
            pnl = -dll - cum - SLIP * PV * q
            low = pnl
        recs.append({"day": day, "entry_t": t["entry_t"], "exit_t": xt, "dir": t["dir"], "exit": ex, "risk": t["risk"],
                     "tgt": t["tgt"], "src": t["src"], "qty": q, "pnl": round(pnl, 2), "low": round(low, 2),
                     "risk_usd": round(t["risk"] * PV * q, 2)})
        busy = xt; n += 1
        if t["src"] == "LIT":
            lit_done = True
        if bal + cum + low <= floor:
            return cum, recs, True
        cum += pnl
    return cum, recs, False


def run_eval(days, by, rule, horizon=20, keep=None, lost=None, max_day=2, pre=False, reserve=True):
    """One MFFU 50K eval over the session list days (tools/lit_adv_manage.run_eval + second strategies). pre: a LIT signal
    while a second-strategy trade is open flattens it at that bar's open (1 tick slippage) and LIT trades (LIT priority);
    else the LIT signal is skipped (counted in lost)."""
    bal = peak = 0.0
    floor = -MLL
    for kk, day in enumerate(days[:horizon]):
        cum, recs, failed = play_day(by.get(day, ()), day, bal, floor, kk + 1, rule, pre, max_day, lost, reserve=reserve)
        if keep is not None:
            keep.extend(recs)
        if failed:
            return "FAIL", kk + 1
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - MLL), LOCK)
        if bal >= TGT:
            return "PASS", kk + 1
    return "OPEN", min(len(days), horizon)


def span_days(span):
    a, z = SPANS[span]
    return [d for d in units()["sessions"] if a <= d <= z]


def score_span(U, rule, span, pre=False, reserve=True):
    by = by_day(U)
    S = span_days(span)
    res = [(run_eval(S[i:i + 20], by, rule, pre=pre, reserve=reserve), len(S) - i) for i in range(len(S))]
    o = {}
    for lab, h in (("10", 10), ("20", 20)):
        R = [r for r, av in res if av >= h]
        N = len(R) or 1
        o["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS" and r[1] <= 20]
    o["pass_med"] = float(np.median(pas)) if pas else None
    # back-to-back eval path ($)
    k, T, n, lost = 0, [], collections.Counter(), []
    while k < len(S):
        r, used = run_eval(S[k:], by, rule, len(S) - k, keep=T, lost=lost, pre=pre, reserve=reserve)
        n[r] += 1
        if r == "OPEN":
            break
        k += used
    p = np.array([t["pnl"] for t in T]) if T else np.zeros(1)
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    o.update(n=len(T), tpw=round(len(T) / (len(S) / 5), 2), net=round(float(p.sum())), per_month=round(float(p.sum()) / (len(S) / 21)),
             dd=round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())), pf=round(float(p[p > 0].sum() / gl), 2) if gl else None,
             win=round(100.0 * float((p > 0).mean()), 1) if T else None, b2b=f"{n['PASS']}/{n['FAIL']}/{n['OPEN']}",
             lit_lost=sum(1 for _, s in lost if s == "LIT"),
             by_src={s: [sum(1 for t in T if t["src"] == s), round(sum(t["pnl"] for t in T if t["src"] == s))]
                     for s in sorted({t["src"] for t in T})})
    o["cost"] = round(PRICE / (o["p10"] / 100.0)) if o["p10"] > 0 else None
    return o, T


def combo_units(subset):
    u = units()
    return list(u["LIT"]) + [t for nm in subset for t in u[nm]]


def score_combo(subset, rule, spans=tuple(SPANS), pre=False):
    U = combo_units(subset)
    return {s: score_span(U, rule, s, pre)[0] for s in spans}


# ================================================================================================ commands
def check():
    """LIT alone through this executor == run lit_adopt_t15_be_off_eval (2-week 57.1/5.9 H1, 52.2/0.0 H2, net +34,234 / +9,059)."""
    o = score_combo((), "usd500", ("H1", "H2"))
    for s in ("H1", "H2"):
        x = o[s]
        print(f"LIT alone {s}: n={x['n']} PF {x['pf']} net {x['net']:+,} DD {x['dd']:,} 2w {x['p10']}/{x['f10']} 1mo {x['p20']}/{x['f20']} "
              f"med {x['pass_med']}", flush=True)
    ok = (o["H1"]["p10"], o["H1"]["f10"], o["H2"]["p10"], o["H2"]["f10"]) == (57.1, 5.9, 52.2, 0.0) and \
        (o["H1"]["net"], o["H2"]["net"]) == (34234, 9059)
    # the Asia-slot run itself (all its trades as LIT units) == run lit_more_ent_asia_slot_rr3_eval (56.3/6.7, 59.4/2.9)
    ua = [t | {"src": "LIT"} for t in units()["_asia_all"]]
    oa = {s: score_span(ua, "usd500", s)[0] for s in ("H1", "H2")}
    print(f"Asia-slot run as stored: H1 2w {oa['H1']['p10']}/{oa['H1']['f10']} net {oa['H1']['net']:+,} | "
          f"H2 2w {oa['H2']['p10']}/{oa['H2']['f10']} net {oa['H2']['net']:+,}", flush=True)
    print("CHECK", "OK" if ok else "DIFF", flush=True)
    return ok, o, oa


RULES = ["usd300", "usd300_safe", "usd300_dll", "usd300_safe_dll", "usd500", "usd500_safe", "usd500_dll", "usd500_safe_dll",
         "need0.25", "need0.5", "need1.0"]
POOL = ("EMA", "MD", "SR", "Asia")


def jobs():
    J = [((), "-")]
    for k in range(1, 5):
        for sub in itertools.combinations(POOL, k):
            if all(s == "Asia" for s in sub):
                J.append((sub, "-"))
            else:
                J += [(sub, r + m) for r in RULES for m in ("", "|pre")]
    return J


def _job(j):
    sub, rule = j
    r0, pre = rule.split("|")[0], rule.endswith("|pre")
    return "+".join(("LIT",) + sub) + "|" + rule, score_combo(sub, r0 if r0 != "-" else "usd500", pre=pre)


def grid(procs=4):
    from multiprocessing import Pool
    units()
    J = jobs()
    print(len(J), "combinations", flush=True)
    with Pool(procs) as pool:
        R = dict(pool.map(_job, J, chunksize=2))
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    out["grid"] = R
    out["n_grid"] = len(R)
    json.dump(out, open(OUT, "w"), indent=1)
    return R


def line(k, o):
    f = lambda s: (f"{o[s]['tpw']}/wk {o[s]['net']:+,} DD {o[s]['dd']:,} 2w {o[s]['p10']}/{o[s]['f10']} 1m {o[s]['p20']}/{o[s]['f20']} "
                   f"med {o[s]['pass_med']} lost {o[s]['lit_lost']}")
    return f"{k:34s} H1[{f('H1')}] H2[{f('H2')}] 25[{o['2025']['net']:+,} 2w {o['2025']['p10']}/{o['2025']['f10']}] " \
           f"21-24[{o['2021-24']['net']:+,} 2w {o['2021-24']['p10']}/{o['2021-24']['f10']}]"


def rank(R, span="H1"):
    """Pick score on one half: 2-week pass - 2 x 2-week fail - 1-month fail (eval odds first), + $ as a tie-break."""
    s = lambda o: o[span]["p10"] - 2.0 * o[span]["f10"] - o[span]["f20"] + o[span]["net"] / 5000.0
    return sorted(R.items(), key=lambda kv: -s(kv[1]))


def show(R=None, top=15):
    R = R or json.load(open(OUT))["grid"]
    base = R["LIT|-"]
    print(line("LIT|-", base))
    for k, o in rank(R)[:top]:
        print(line(k, o))


# ================================================================================================ part 2: separate accounts
FD = dict(SZ.FD_50K)
LIT_FUNDED = {"mode": "safe_eval", "safe_cap": 0.6, "pass_lock": False}      # LIT on a funded account: $800/20-pt micros capped at 60% of the room
SEP_RULES = ["usd300", "usd300_safe", "usd500", "usd500_safe", "need0.5", "need1.0"]
SEP_ACCTS = [("EMA",), ("MD",), ("SR",), ("EMA", "SR"), ("EMA", "MD", "SR")]


def acct_units(names, nohedge=False):
    u = units()
    U = [t for nm in names for t in u[nm]]
    return no_hedge(U) if nohedge else U


def no_hedge(U):
    """MFFU forbids long and short on the same underlying at the same time, also across accounts. With LIT trading on the
    other account (LIT priority: every LIT signal assumed taken there): a second-strategy trade is skipped when a LIT trade is
    open in the opposite direction at its entry, and flattened at a LIT entry in the opposite direction while it is open."""
    by = collections.defaultdict(list)
    for t in units()["LIT"]:
        by[t["day"]].append(t)
    out = []
    for t in U:
        if t["src"] in LITLIKE:
            out.append(t); continue
        L = [x for x in by.get(t["day"], ()) if x["dir"] != t["dir"]]
        if any(x["entry_t"] <= t["entry_t"] < x["exit_t"] for x in L):
            continue
        nxt = min((x["entry_t"] for x in L if t["entry_t"] < x["entry_t"] < t["exit_t"]), default=None)
        if nxt is not None:
            pts, w1 = cut_at(t, nxt)
            t = {**t, "pts": pts, "w1": w1, "exit_t": nxt, "exit": "HEDGE"}
        out.append(t)
    return out


def run_funded(days, by, rule, pre=False, reserve=True):
    """One MFFU Builder 50K sim-funded account (start $0, EOD trailing $2,000 locked at +$100, soft daily loss $1,000, buffer
    $2,100, payouts $500-$2,000 at 80%, 2 traded days a cycle, best day <= 50% of the cycle, 5 payouts) over the session
    list. Second strategies: their eval rule with need* replaced by usd300_safe; LIT: LIT_FUNDED."""
    frule = "usd300_safe" if rule.startswith("need") else rule
    bal = peak = 0.0
    floor = -FD["mll"]
    paid, n_pay, last_bal, cyc = 0.0, 0, 0.0, []
    for k, day in enumerate(days):
        cum, recs, failed = play_day(by.get(day, ()), day, bal, floor, 99, frule, pre, litcfg=LIT_FUNDED, dll=FD["dll"], reserve=reserve)
        if failed:
            return {"paid": paid, "n": n_pay, "blown": k + 1}
        bal += cum
        if bal <= floor:
            return {"paid": paid, "n": n_pay, "blown": k + 1}
        peak = max(peak, bal)
        floor = min(max(floor, peak - FD["mll"]), FD["lock"])
        if recs:
            cyc.append(cum)
        if k + 1 < FD["first_wait"] or len(cyc) < FD["cycle_days"]:
            continue
        prof = bal - last_bal
        if prof <= 0 or max(cyc) > FD["cons"] * prof:
            continue
        amt = min(bal - FD["buffer"], FD["pay_max"])
        if amt < FD["pay_min"]:
            continue
        paid += amt * FD["split"]; n_pay += 1; bal -= amt; last_bal, cyc = bal, []
        if n_pay >= FD["max_payouts"]:
            return {"paid": paid, "n": n_pay, "blown": None, "grad": k + 1}
    return {"paid": paid, "n": n_pay, "blown": None}


ALL = ("2021-11-01", "2026-12-31")


def sep_score(U, rule, span, pre=False, reserve=True):
    """Eval odds (fresh start every session of the span, 20 sessions inside the span), eventual pass within 60 sessions
    (sessions may run past the span; starts with 60 sessions of data), funded $ in 3 / 6 months (63 / 126 sessions from
    every start of the span that has them) and $ per eval bought = P(pass in 60) x funded $ (3 months) - $91.80."""
    by = by_day(U)
    allS = units()["sessions"]
    a, z = SPANS.get(span, ALL)
    ix = [i for i, d in enumerate(allS) if a <= d <= z]
    S = [allS[i] for i in ix]
    res = [(run_eval(S[i:i + 20], by, rule, pre=pre, reserve=reserve), len(S) - i) for i in range(len(S))]
    o = {}
    for lab, h in (("10", 10), ("20", 20)):
        R = [r for r, av in res if av >= h]
        N = len(R) or 1
        o["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS" and r[1] <= 20]
    o["pass_med"] = float(np.median(pas)) if pas else None
    E = [run_eval(allS[i:i + 60], by, rule, 60, pre=pre, reserve=reserve) for i in ix if i + 60 <= len(allS)]
    o["n60"] = len(E)
    o["p60"] = round(100.0 * sum(1 for r in E if r[0] == "PASS") / len(E), 1) if E else None
    o["f60"] = round(100.0 * sum(1 for r in E if r[0] == "FAIL") / len(E), 1) if E else None
    for lab, h in (("3m", 63), ("6m", 126)):
        Fd = [run_funded(allS[i:i + h], by, rule, pre=pre, reserve=reserve) for i in ix if i + h <= len(allS)]
        o["fund_n_" + lab] = len(Fd)
        o["fund_paid_" + lab] = round(float(np.mean([f["paid"] for f in Fd]))) if Fd else None
        o["fund_lost_" + lab] = round(100.0 * sum(1 for f in Fd if f["blown"]) / len(Fd), 1) if Fd else None
    if o["p60"] is not None and o["fund_paid_3m"] is not None:
        o["ev_eval_3m"] = round(o["p60"] / 100.0 * o["fund_paid_3m"] - PRICE)
    if o["p60"] is not None and o["fund_paid_6m"] is not None:
        o["ev_eval_6m"] = round(o["p60"] / 100.0 * o["fund_paid_6m"] - PRICE)
    o["cost_per_pass"] = round(PRICE / (o["p60"] / 100.0)) if o.get("p60") else None
    return o


SEP_SPANS = ("H1", "H2", "2025", "2021-24", "all")


def _sep_job(j):
    names, rule, pre, *nh = j
    nh = bool(nh and nh[0])
    lit_in = "LIT" in names
    U = acct_units(names, nohedge=nh)
    return ("+".join(names) + "|" + rule + ("|pre" if pre else "") + ("|nohedge" if nh else ""),
            {s: sep_score(U, rule, s, pre, reserve=lit_in) for s in SEP_SPANS})


def separate(procs=4, extra=()):
    from multiprocessing import Pool
    units()
    J = ([(n, r, False, nh) for n in SEP_ACCTS for r in SEP_RULES for nh in (False, True)] + [(("LIT",), "usd500", False)]
         + [(("LIT", "EMA", "Asia"), "need1.0", False), (("LIT", "MD"), "need1.0", False), (("LIT", "EMA"), "usd500_safe", False),
            (("LIT", "EMA", "Asia"), "usd300_safe", False)] + list(extra))
    with Pool(procs) as pool:
        R = dict(pool.map(_sep_job, J, chunksize=1))
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    out.setdefault("separate", {}).update(R)
    json.dump(out, open(OUT, "w"), indent=1)
    for k, o in R.items():
        print(sep_line(k, o), flush=True)
    return R


def sep_line(k, o):
    f = lambda s: (f"2w {o[s]['p10']}/{o[s]['f10']} 1m {o[s]['p20']}/{o[s]['f20']} 60s {o[s]['p60']}/{o[s]['f60']} "
                   f"fund3m ${o[s]['fund_paid_3m']} lost {o[s]['fund_lost_3m']}% ev ${o[s].get('ev_eval_3m')}")
    return f"{k:24s} H1[{f('H1')}] H2[{f('H2')}] 25[{f('2025')}] 21-24[{f('2021-24')}] all6m[${o['all']['fund_paid_6m']} lost {o['all']['fund_lost_6m']}% ev ${o['all'].get('ev_eval_6m')}]"


# ================================================================================================ picks + store
# (key, run id, title, units names, rule, pre, nohedge, status)
PICKS = [
    ("LIT|-", "mix_lit_alone", "LIT alone on the eval (this executor = run lit_adopt_t15_be_off_eval)", ("LIT",), "usd500", False, False, "info"),
    ("B:EMA+MD+SR|need1.0|nohedge", "mix_acct2_ema_md_sr_need1", "Second Builder 50K: EMA + MACD + S/R together, LIT's two_week need size, "
     "no-hedge guard vs LIT's account", ("EMA", "MD", "SR"), "need1.0", False, True, "promising"),
    ("B:EMA+MD+SR|usd300_safe|nohedge", "mix_acct2_ema_md_sr_300safe", "Second Builder 50K: EMA + MACD + S/R together at $300 risk, "
     "60% room cap, no-hedge guard", ("EMA", "MD", "SR"), "usd300_safe", False, True, "info"),
    ("LIT+EMA+Asia|need1.0", "mix_lit_ema_asia_need1", "One eval: LIT + EMA + Asia slot, EMA at LIT's need size", ("LIT", "EMA", "Asia"),
     "need1.0", False, False, "promising"),
    ("LIT+MD|need1.0", "mix_lit_md_need1", "One eval: LIT + MACD sweep at LIT's need size (H1 pick, fails the H2 check)", ("LIT", "MD"),
     "need1.0", False, False, "rejected"),
    ("LIT+EMA|usd500_safe", "mix_lit_ema_500safe", "One eval: LIT + EMA at $500 risk, 60% room cap", ("LIT", "EMA"), "usd500_safe",
     False, False, "rejected"),
]


def pick_numbers():
    """Full numbers of the picks: eval odds, $ on the back-to-back eval path, per span; + the stored path trades."""
    out, paths = {}, {}
    for key, rid, title, names, rule, pre, nh, status in PICKS:
        lit_in = "LIT" in names
        U = acct_units(names, nohedge=nh)
        o, P = {}, []
        for sp in SPANS:
            x, T = score_span(U, rule, sp, pre, reserve=lit_in)
            o[sp] = x
            P += T
        out[key] = o
        paths[key] = P
    return out, paths


def two_acct(o, paths, b="B:EMA+MD+SR|need1.0|nohedge"):
    """Account A (LIT alone) + account B, $ added up per day (two eval paths side by side)."""
    res = {}
    for sp in SPANS:
        S = span_days(sp)
        d = collections.defaultdict(float)
        for k in ("LIT|-", b):
            for t in paths[k]:
                if t["day"] in S:
                    d[t["day"]] += t["pnl"]
        eq = np.cumsum([d.get(x, 0.0) for x in S])
        dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(eq) else 0.0
        res[sp] = {"net": round(float(eq[-1])), "dd": round(dd), "per_month": round(float(eq[-1]) / (len(S) / 21))}
    return res


def store(o, paths):
    from tools import runlib as rl
    Q = "Owner 2026-10-22: what is the best way to combine LIT with the second strategies (EMA, MACD, S/R, Asia slot), in $ and eval odds?"
    sess = [d for d in units()["sessions"] if d >= "2021-01-01"]
    for key, rid, title, names, rule, pre, nh, status in PICKS:
        T = []
        for t in paths[key]:
            T.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
                      "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0, "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"],
                      "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": t["src"], "mfe": None, "mae": None,
                      "bars_held": None, "regime": "", "mult": None, "low": t["low"]})
        x = o[key]
        f = lambda s: (f"{x[s]['tpw']}/wk net {x[s]['net']:+,} (${x[s]['per_month']:,}/mo) DD {x[s]['dd']:,}; 2-week pass/fail "
                       f"{x[s]['p10']}/{x[s]['f10']}, 1 month {x[s]['p20']}/{x[s]['f20']}, median {x[s]['pass_med']} sessions")
        rl.save(rid, title, "other", Q, params={"accounts": names, "second_size": rule, "lit_preempts": pre, "no_hedge": nh},
                sizing={"lit": "two_week (live lit_sizing)", "second": rule}, trades=T, scored=rl.score(T, sess), status=status,
                verdict=f"Eval path (fresh eval every session, 20 sessions; $ = back-to-back eval path). 2026 H1 (pick) {f('H1')}. "
                        f"H2 (check) {f('H2')}. Reference 2025 {f('2025')}; 2021-24 {f('2021-24')} (LIT on 5m there).",
                notes="tools/second_mix.py (PICKS); stored trades = the back-to-back eval path of each span (2021-24, 2025, H1, H2); "
                      "the run library's own eval columns re-score that path by day and are not the published odds (those are in the verdict).",
                writeup="second-mix", tags=["second", "mix"])
        print("saved", rid, flush=True)


def picks(save=False):
    o, paths = pick_numbers()
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    out["picks"] = o
    out["two_accounts"] = {"A=LIT|-, B=EMA+MD+SR|need1.0|nohedge": two_acct(o, paths),
                           "A=LIT|-, B=EMA+MD+SR|usd300_safe|nohedge": two_acct(o, paths, "B:EMA+MD+SR|usd300_safe|nohedge")}
    json.dump(out, open(OUT, "w"), indent=1)
    for k, x in o.items():
        print(k, {s: (x[s]["tpw"], x[s]["net"], x[s]["dd"], x[s]["p10"], x[s]["f10"], x[s]["p20"], x[s]["f20"], x[s]["pass_med"], x[s]["lit_lost"], x[s]["by_src"]) for s in SPANS})
    print(json.dumps(out["two_accounts"]))
    if save:
        store(o, paths)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "units":
        build_units()
    elif cmd == "check":
        check()
    elif cmd == "grid":
        show(grid())
    elif cmd == "show":
        show()
    elif cmd == "separate":
        separate()
    elif cmd in ("picks", "save"):
        picks(save=cmd == "save")
