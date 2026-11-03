"""ATLAS v2 (2026-10-25): make ATLAS (account B, MFFU Builder 25K) stronger where the audit found it weak.

Research only: nothing here touches second_model.json, account_b or any live file. Executor = tools/atlas.py (the real
account-B rules: need size, one position, max 2 a day, never opposite LIT incl. LIT's armed setups, $600 soft daily loss,
stuck under $100), which reproduces today's base exactly (H1 65.5 / H2 43.5 2-week pass, path +$6,481 / +$4,434).

New here (all pre-declared in FAMILIES, few variants each):
  * new members: the stop-hunt candidates sh_asia (SHA) and sh_trend (SHT; SHT1 = its first trade a day only), from their
    stored research trades (research/stophunt/*.json), converted to account-B units the way second_mix.second_units does
  * regime gates PICKED ON 2021-24 ONLY (VIX tercile, ATR percentile, weekday, entry-hour bucket, each known before the
    trade) and then checked on 2025 + 2026 H1 + H2, with a same-size random-skip placebo
  * member drops / weights re-judged on the v2 rule (2026 both halves AND the 5-year reference)
  * eval-path rules: stuck threshold, "idle after session N" rule, the session-10 30% room cap, scored as money per
    $63 eval bought (eval P&L is not withdrawable: passes x the funded payout - fees is the real money)

    python -X utf8 tools/atlas_v2.py units        # build the hunt units (cache research/runs/_cache/atlas_v2_sh_units.pkl)
    python -X utf8 tools/atlas_v2.py grid         # every family -> research/second/atlas_v2_grid.json + report
    python -X utf8 tools/atlas_v2.py placebo      # random-skip placebos of the regime gates
    python -X utf8 tools/atlas_v2.py save         # runs atlas_v2_* in the run library
Paper research only.
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import os
import pickle
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import atlas as A  # noqa: E402
from tools import second_mix as M  # noqa: E402
from tools import second_account_b as AB  # noqa: E402

SPANS = A.SPANS
SH = {"SHA": "sh_asia_resweep.json", "SHT": "sh_trend_idm5.json"}
SH_CACHE = os.path.join(ROOT, "research", "runs", "_cache", "atlas_v2_sh_units.pkl")
OUT = os.path.join(ROOT, "research", "second", "atlas_v2_grid.json")
PRICE = 63.0
KEYS = {"EMA": "ema_lon_vix", "MD": "macd_sweep", "SR": "sr_nyreclaim", "SHA": "sh_asia", "SHT": "sh_trend", "SHT1": "sh_trend"}


# ================================================================================================ hunt units
_BARS = {}


def _sh_units(nm, trades=None):
    """research/stophunt/<pick>.json trades (or a given trade list) -> account-B units (second_mix.second_units, same path
    fields)."""
    from tools import lit_final as F
    if "b" not in _BARS:
        Mk, _ = F.market("cisd", [])
        _BARS["b"] = (F.bars(Mk, "5m"), F.bars(Mk, "1m"))
    B5, B1 = _BARS["b"]
    if trades is None:
        trades = json.load(open(os.path.join(ROOT, "research", "stophunt", SH[nm]), encoding="utf-8"))["trades"]
    out = []
    for t in trades:
        dr = int(t["dir"])
        e, s, x = float(t["entry"]), float(t["stop"]), float(t["exit"])
        risk = abs(e - s)
        if risk <= 0:
            continue
        pts = (x - e) * dr
        tgt = abs(float(t["target"]) - e) if t.get("target") is not None else 2.0 * risk
        B = B1 if int(t["entry_t"]) >= int(B1.t[0]) + 86400 else B5
        k0 = int(np.searchsorted(B.t, int(t["entry_t"]), side="right"))
        kx = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
        lo = B.l if dr == 1 else -B.h
        w = float(lo[k0:kx].min()) - e * dr if kx > k0 else 0.0
        w1 = max(-(risk + 0.25), min(0.0, w, pts))
        op = (B.o[k0:kx + 1] * dr - e * dr) if kx >= k0 else np.zeros(0)
        lw = np.minimum.accumulate(np.r_[0.0, lo[k0:kx] - e * dr]) if kx >= k0 else np.zeros(0)
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": dr, "exit": t["exit_kind"],
                    "risk": round(risk, 4), "tgt": round(tgt, 4), "pts": round(pts, 4), "w1": round(w1, 4), "src": nm,
                    "pt": B.t[k0:kx + 1].astype(np.int64), "po": np.round(op, 2), "pw": np.maximum(np.round(lw, 2), -(risk + 0.25))})
    return out


def sh_units():
    from tools import runlib as _rl
    path = _rl.keyed(SH_CACHE)                  # keyed by the NQ data (2026-11-03: never a sandbox run's units)
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    U = {nm: _sh_units(nm) for nm in SH}
    seen, first = set(), []
    for u in sorted(U["SHT"], key=lambda u: u["entry_t"]):
        if u["day"] not in seen:
            seen.add(u["day"])
            first.append({**u, "src": "SHT1"})
    U["SHT1"] = first
    pickle.dump(U, open(path, "wb"))
    return U


PL_CACHE = os.path.join(ROOT, "research", "runs", "_cache", "atlas_v2_placebo_members.pkl")


def placebo_members(n=20):
    """Placebo members with each hunt's own mechanics (tools/stophunt_audit.placebo_rows): 'rtime' = same side, a random
    5m signal bar of the same session bucket in a random session of the same span (n seeds); 'flip' = same signal bar,
    the other side. Units keyed PSHA_r<k> / PSHT_r<k> / PSHA_f / PSHT_f."""
    if os.path.exists(PL_CACHE):
        P = pickle.load(open(PL_CACHE, "rb"))
        if len([k for k in P if k.startswith("PSHA_r")]) >= n:
            return P
    from tools import stophunt_audit as SA
    P = {}
    for nm, lead in (("SHA", "asia"), ("SHT", "trend")):
        cfg = SA.LEADS[lead]
        rows = json.load(open(os.path.join(ROOT, "research", "stophunt", SH[nm]), encoding="utf-8"))["trades"]
        for k in range(n):
            pr = SA.placebo_rows(cfg, rows, "rtime", 100 + k)
            P[f"P{nm}_r{k}"] = [{**u, "src": nm} for u in _sh_units(nm, pr)]
        pr = SA.placebo_rows(cfg, rows, "flip", 100)
        P[f"P{nm}_f"] = [{**u, "src": nm} for u in _sh_units(nm, pr)]
        print(nm, "placebo members built", flush=True)
    pickle.dump(P, open(PL_CACHE, "wb"))
    return P


def install():
    """Put the hunt units into second_mix's unit cache (tools/atlas.member_units then reads them like any member)."""
    U = M.units()
    if "SHA" not in U:
        U.update(sh_units())
    return U


# ================================================================================================ facts known before the trade
_F = {}


def atr_pct():
    """day -> percentile (0-100) of the prior session's daily ATR(14) within the trailing 252 sessions (data/NQ_1d.csv,
    CME NQ1! TradingView export). Known before the day opens."""
    if "a" not in _F:
        import pandas as pd
        d = pd.read_csv(os.path.join(ROOT, "data", "NQ_1d.csv"))
        # TradingView daily bars are stamped at the session's 18:00 ET open; label each bar by its trading day
        import zoneinfo
        ET = zoneinfo.ZoneInfo("America/New_York")
        lab = []
        for t in d["time"]:
            x = dt.datetime.fromtimestamp(int(t), ET)
            if x.hour >= 17:
                x = x + dt.timedelta(days=1)
            while x.weekday() >= 5:
                x = x + dt.timedelta(days=1)
            lab.append(x.date().isoformat())
        h, l, c = d["high"].values, d["low"].values, d["close"].values
        pc = np.r_[c[0], c[:-1]]
        tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
        atr = pd.Series(tr).rolling(14).mean().values
        out = {}
        import bisect
        for i in range(len(lab)):
            j = i - 1                                    # the prior completed session
            if j < 266 or np.isnan(atr[j]):
                continue
            w = atr[j - 251:j + 1]
            out[lab[i]] = float(100.0 * (w < atr[j]).mean())
        S = M.units()["sessions"]
        res = {}
        for s in S:
            if s in out:
                res[s] = out[s]
            else:                                        # a session label not in the daily file: nearest earlier label
                k = bisect.bisect_right(sorted(out), s) - 1
                res[s] = out[sorted(out)[k]] if k >= 0 else float("nan")
        _F["a"] = res
    return _F["a"]


def fact(u, f):
    if f == "vix":
        return A.vix_prev().get(u["day"], float("nan"))
    if f == "atrp":
        return atr_pct().get(u["day"], float("nan"))
    if f == "dow":
        return dt.date.fromisoformat(u["day"]).weekday()
    if f == "hour":
        return A.et_mod(u["entry_t"]) // 60
    raise KeyError(f)


# ================================================================================================ variant = tools/atlas V + v2 keys
_mu = A.member_units


def member_units(name, V):
    sub = (V.get("sub") or {}).get(name)            # placebo: another unit set in this member's place (same weight/gate)
    if sub:
        U = _mu(name, {**V, "flt": {}})
        U = M.units()[sub]
    else:
        U = _mu(name, V)
    g = (V.get("gate") or {}).get(name)
    drop = set((V.get("drop") or {}).get(name) or ())
    if not g and not drop:
        return U
    out = []
    for u in U:
        if u["entry_t"] in drop:
            continue
        if g:
            x = fact(u, g["f"])
            if any(lo <= x < hi for lo, hi in g["out"]):
                continue
        out.append(u)
    return out


A.member_units = member_units

EV = {"min_room": 100.0, "idle": None}


def run_eval(days, by, rule, horizon=20, keep=None):
    """tools/second_account_b.run_eval + the v2 eval rules: stuck under min_room, and "idle" [session, room]: from that
    session on, an eval with less room than that is treated as stuck (buy a new one)."""
    bal = peak = 0.0
    floor = -M.MLL
    idle = EV["idle"]
    for kk, day in enumerate(days[:horizon]):
        cum, recs, failed = M.play_day(by.get(day, ()), day, bal, floor, kk + 1, rule, False, 2, None, reserve=False)
        if keep is not None:
            keep.extend(recs)
        if failed:
            return "FAIL", kk + 1, 0.0
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1, 0.0
        peak = max(peak, bal)
        floor = min(max(floor, peak - M.MLL), M.LOCK)
        if bal >= M.TGT:
            return "PASS", kk + 1, bal - floor
        room = bal - floor
        if room < EV["min_room"] or (idle and kk + 1 >= idle[0] and room < idle[1]):
            return "STUCK", kk + 1, room
    return "OPEN", min(len(days), horizon), bal - floor


AB.run_eval = run_eval


def multi_path(by, rule, span, step=5):
    """The back-to-back eval path started on every 5th session of the span (the published path is one start only):
    mean trading $ less fees, mean passes, mean evals bought, $ per eval bought."""
    allS = M.units()["sessions"]
    a, z = M.SPANS[span]
    S = [d for d in allS if a <= d <= z]
    rows = []
    for k0 in range(0, max(1, len(S) - 20), step):
        k, T, n = k0, [], collections.Counter()
        while k < len(S):
            r, used, _ = run_eval(S[k:], by, rule, len(S) - k, keep=T)
            n[r] += 1
            if r == "OPEN":
                break
            k += used
        bought = n["PASS"] + n["FAIL"] + n["STUCK"] + (1 if n["OPEN"] else 0)
        net = sum(t["pnl"] for t in T)
        rows.append((net - PRICE * bought, n["PASS"], bought, len(S) - k0))
    R = np.array(rows, float)
    return {"mp_net_less_fees": round(float(R[:, 0].mean())), "mp_passes": round(float(R[:, 1].mean()), 2),
            "mp_bought": round(float(R[:, 2].mean()), 2), "mp_starts": len(rows),
            "mp_per_eval": round(float(R[:, 0].sum() / R[:, 2].sum())),
            "mp_pass_per_eval": round(float(R[:, 1].sum() / R[:, 2].sum()), 3),
            "mp_pass_per_month": round(float((R[:, 1] / (R[:, 3] / 21.0)).mean()), 2)}


def weeks2(T, span):
    allS = M.units()["sessions"]
    a, z = M.SPANS[span]
    S = [d for d in allS if a <= d <= z]
    wk = lambda d: dt.date.fromisoformat(d).isocalendar()[:2]
    W = collections.Counter(wk(t["day"]) for t in T)
    allw = sorted({wk(d) for d in S})
    return round(100.0 * sum(1 for w in allw if W.get(w, 0) >= 2) / max(1, len(allw)), 1)


def sig_per_week(U, span):
    """Candidate trades a week after the no-hedge rules (before sizing / eval state): what the owner sees as frequency."""
    allS = M.units()["sessions"]
    a, z = M.SPANS[span]
    S = [d for d in allS if a <= d <= z]
    n = sum(1 for u in U if a <= u["day"] <= z)
    wk = lambda d: dt.date.fromisoformat(d).isocalendar()[:2]
    W = collections.Counter(wk(u["day"]) for u in U if a <= u["day"] <= z)
    allw = sorted({wk(d) for d in S})
    return round(n / (len(S) / 5), 2), round(100.0 * sum(1 for w in allw if W.get(w, 0) >= 2) / max(1, len(allw)), 1)


def score(V, spans=SPANS, mp=True, keep_paths=False):
    EV["min_room"] = float(V.get("min_room", 100.0))
    EV["idle"] = V.get("idle")
    keep = AB.MIN_ROOM
    U = A.account_units(V)
    out, paths = {}, {}
    try:
        with A.Plan(V) as pl:
            for s in spans:
                o, T = AB.score(U, "atlas", s, V.get("frule") or pl.safe_rule)
                o["wk2"] = weeks2(T, s)
                o["sig_tpw"], o["sig_wk2"] = sig_per_week(U, s)
                o["passes"] = int(o["b2b"].split("/")[0])
                o["fees"] = round(PRICE * o["evals_bought"])
                o["per_eval"] = round(o["path_net_less_fees"] / max(1, o["evals_bought"]))
                # real money proxy: each pass becomes a funded 25K worth its span's 3-month payout (fund_paid_3m)
                fp = o.get("fund_paid_3m") or 0
                o["real_3m"] = round(o["passes"] * fp - o["fees"])
                if mp:
                    o.update(multi_path(M.by_day(U), "atlas", s))
                out[s] = o
                if keep_paths:
                    paths[s] = T
    finally:
        AB.MIN_ROOM = keep
        EV["min_room"], EV["idle"] = 100.0, None
    return (out, paths) if keep_paths else out


# ================================================================================================ judging
MONEY = "mp_net_less_fees"   # eval-path $ less the $63 fees, averaged over back-to-back paths started every 5th session
# (the published path is ONE start and hangs on it: ATLAS + both hunts shows H2 +$1.2k on it, one eval open all of H2,
# against +$4.8k averaged over starts; both are reported, the average decides)


def better2026(x, b, fam=""):
    """The owner's test in one 2026 half: 2-week pass up or equal, dead (fail + stuck) not up, eval-path $ up.
    Eval-rule families (buying a new eval earlier raises "stuck" by design): $ per eval bought up and $ not down."""
    if fam.startswith("eval"):
        return x["mp_per_eval"] > b["mp_per_eval"] and x[MONEY] >= b[MONEY] and x["p10"] >= b["p10"]
    return x["p10"] >= b["p10"] and x["dead10"] <= b["dead10"] and x[MONEY] > b[MONEY]


def verdict(o, base, fam=""):
    """v2 rule: better in H1 (pick) AND H2 (check), AND the 5-year reference does not lose: 2025 and 2021-24 money less
    fees each >= 0 (tier A), or at least not worse than today's (tier B). Frequency: 2+ candidate trades a week in every
    span."""
    h1 = better2026(o["H1"], base["H1"], fam)
    h2 = better2026(o["H2"], base["H2"], fam)
    r25, r24 = o["2025"][MONEY], o["2021-24"][MONEY]
    b25, b24 = base["2025"][MONEY], base["2021-24"][MONEY]
    freq = all(o[s]["sig_tpw"] >= 2.0 for s in SPANS)
    tier = "A" if (r25 >= 0 and r24 >= 0) else "B" if (r25 >= b25 and r24 >= b24) else "-"
    return {"h1": h1, "h2": h2, "both": h1 and h2, "ref": tier, "freq": freq, "pass": h1 and h2 and tier != "-" and freq}


# ================================================================================================ families
def V_(**kw):
    V = copy.deepcopy(A.BASE)
    V.update(copy.deepcopy(kw))
    return V


MEM3 = ["EMA", "MD", "SR"]


def fam_members():
    out = []
    for add in (["SHA"], ["SHT"], ["SHT1"], ["SHA", "SHT"], ["SHA", "SHT1"]):
        out.append(("hunt_member", "+".join(add), V_(members=MEM3 + add)))
    # a hunt replacing the weakest-5-year member (EMA: PF 1.05 in 2021-24 at $500)
    out.append(("hunt_member", "MD+SR+SHA+SHT", V_(members=["MD", "SR", "SHA", "SHT"])))
    out.append(("hunt_member", "MD+SR+SHA", V_(members=["MD", "SR", "SHA"])))
    # drops (re-judged on the v2 rule)
    for keep in (["MD", "SR"], ["EMA", "SR"], ["EMA", "MD"]):
        out.append(("drop", "+".join(keep), V_(members=keep)))
    # weights by the 5-year record: EMA (weakest) down
    for w in (0.5, 0.75):
        out.append(("weight", f"EMA{w:g}", V_(w={"EMA": w})))
    return out


def gate_picks():
    """Pre-declared rule, 2021-24 ONLY: per member x fact, cut the fact into 3 buckets (VIX / ATR-pct terciles of that
    member's 2021-24 trades; weekday; entry hour), and pick the single worst bucket if its mean R < 0 with n >= 30.
    Nothing from 2025 or 2026 is used to choose."""
    install()
    picks = []
    for nm in MEM3:
        U = [u for u in M.units()[nm] if "2021-01-01" <= u["day"] <= "2024-12-31"]
        R = np.array([(u["pts"] - 0.95) / u["risk"] for u in U])
        for f in ("vix", "atrp", "dow", "hour"):
            x = np.array([fact(u, f) for u in U], float)
            ok = ~np.isnan(x)
            if f in ("vix", "atrp"):
                q1, q2 = np.quantile(x[ok], [1 / 3, 2 / 3])
                B = [(-1e9, float(q1)), (float(q1), float(q2)), (float(q2), 1e9)]
            elif f == "dow":
                B = [(d, d + 1) for d in range(5)]
            else:
                hs = sorted(set(int(v) for v in x[ok]))
                B = [(h, h + 1) for h in hs]
            rows = []
            for lo, hi in B:
                m = ok & (x >= lo) & (x < hi)
                if m.sum() >= 30:
                    rows.append((float(R[m].mean()), int(m.sum()), lo, hi))
            if not rows:
                continue
            worst = min(rows)
            if worst[0] < 0:
                picks.append({"member": nm, "f": f, "out": [[worst[2], worst[3]]], "r2124": round(worst[0], 3), "n2124": worst[1],
                              "buckets": [[round(r, 3), n, lo, hi] for r, n, lo, hi in rows]})
    return picks


def fam_gates():
    out = []
    P = gate_picks()
    for p in P:
        lab = f"{p['member']}_{p['f']}_out{p['out'][0][0]:g}-{p['out'][0][1]:g}"
        out.append(("gate", lab, V_(gate={p["member"]: {"f": p["f"], "out": p["out"]}})))
    # all of one member's picks at once
    by = collections.defaultdict(list)
    for p in P:
        by[p["member"]].append(p)
    return out, P


def fam_eval():
    out = []
    for mr in (150.0, 200.0, 300.0):
        out.append(("eval_stuck", f"stuck<{mr:g}", V_(min_room=mr)))
    for s, r in ((10, 300.0), (11, 300.0), (15, 300.0), (11, 400.0), (15, 500.0)):
        out.append(("eval_idle", f"idle_s{s}_room<{r:g}", V_(idle=[s, r])))
    for un, sc in ((15, 0.3), (20, 0.3), (99, 0.3), (10, 0.5), (15, 0.5)):
        out.append(("eval_cap", f"need_until{un}_safe{sc:g}", V_(cfg={"two_week_until": un, "safe_cap": sc})))
    return out


def fam_sizing():
    """The 5-year loss sits in the "need" size (every member makes money at a flat $500 in every span): 3 smaller sizes."""
    return [("sizing", "room0.4", V_(tw={"room_f": 0.4})), ("sizing", "max_usd300", V_(tw={"max_usd": 300.0})),
            ("sizing", "safe150", V_(size="safe"))]


def fam_hunt2():
    """Round 2, declared after round 1 showed the trend hunt lifts money in all four spans but costs 5 points of H1 2-week
    pass (it crowds the one position / 2 a day): smaller hunt size, or hunts only outside the members' 03:00-12:00 hours."""
    out = []
    for w in (0.5, 0.75):
        out.append(("hunt2", f"SHT_w{w:g}", V_(members=MEM3 + ["SHT"], w={"SHT": w})))
    out.append(("hunt2", "SHT_eve18-02", V_(members=MEM3 + ["SHT"], gate={"SHT": {"f": "hour", "out": [[2, 18]]}})))
    out.append(("hunt2", "SHT_not03-12", V_(members=MEM3 + ["SHT"], gate={"SHT": {"f": "hour", "out": [[3, 12]]}})))
    out.append(("hunt2", "SHT1_w0.75", V_(members=MEM3 + ["SHT1"], w={"SHT1": 0.75})))
    out.append(("hunt2", "SHA+SHT_w0.5", V_(members=MEM3 + ["SHA", "SHT"], w={"SHA": 0.5, "SHT": 0.5})))
    out.append(("hunt2", "SHA_w0.5+SHT", V_(members=MEM3 + ["SHA", "SHT"], w={"SHA": 0.5})))
    out.append(("hunt2", "SHA+SHT_not03-12", V_(members=MEM3 + ["SHA", "SHT"], gate={"SHT": {"f": "hour", "out": [[3, 12]]}})))
    return out


H5 = ["EMA", "MD", "SR", "SHA", "SHT"]
EMA_H6 = {"EMA": {"f": "hour", "out": [[6, 7]]}}


def fam_round3():
    """Round 3 = plateau check of the round-2 pick (both hunts at half size) + what stacks on it. Not a new search."""
    out = []
    for a, b in ((0.4, 0.4), (0.6, 0.6), (0.75, 0.75), (0.5, 0.75), (0.75, 0.5), (0.5, 0.4), (0.4, 0.5)):
        out.append(("plateau", f"SHA{a:g}+SHT{b:g}", V_(members=H5, w={"SHA": a, "SHT": b})))
    W5 = {"SHA": 0.5, "SHT": 0.5}
    out.append(("stack", "H5w0.5+EMA_no06", V_(members=H5, w=W5, gate=EMA_H6)))
    out.append(("stack", "H5w0.5+stuck<150", V_(members=H5, w=W5, min_room=150.0)))
    # added after the eval table showed buying a new eval earlier lifts passes per month (2 more variants, counted)
    out.append(("stack", "H5w0.5+stuck<200", V_(members=H5, w=W5, min_room=200.0)))
    out.append(("stack", "H5w0.5+stuck<300", V_(members=H5, w=W5, min_room=300.0)))
    out.append(("stack", "H5w0.5+need_until10_safe0.5", V_(members=H5, w=W5, cfg={"two_week_until": 10, "safe_cap": 0.5})))
    out.append(("stack", "H5w0.5+SHT_eve", V_(members=H5, w=W5, gate={"SHT": {"f": "hour", "out": [[2, 18]]}})))
    out.append(("stack", "today+EMA_no06+SHT_eve", V_(members=MEM3 + ["SHT"], gate={**EMA_H6, "SHT": {"f": "hour", "out": [[2, 18]]}})))
    return out


def families():
    F = [("base", "today", V_())]
    F += fam_members()
    G, P = fam_gates()
    F += G
    F += fam_eval()
    F += fam_sizing()
    F += fam_hunt2()
    F += fam_round3()
    return F, P


def _job(x):
    fam, name, V = x
    try:
        return fam, name, V, score(V)
    except Exception as e:
        import traceback
        return fam, name, V, {"error": f"{e.__class__.__name__}: {e}", "tb": traceback.format_exc()[-800:]}


def warm():
    install(); M.units(); A.ARM.windows(); A.vix_prev(); atr_pct()


def run(F, procs=4):
    from multiprocessing import Pool
    warm()
    with Pool(procs) as P:
        return P.map(_job, F, chunksize=1)


KEEP = ("p10", "f10", "s10", "dead10", "dec10", "p15", "f15", "p20", "f20", "pass_med", "slow_pass", "p60", "n", "tpw", "wk2",
        "sig_tpw", "sig_wk2", "net", "per_month", "dd", "pf", "b2b", "passes", "evals_bought", "fees", "path_net_less_fees",
        "per_eval", "fund_paid_3m", "fund_lost_3m", "real_3m", "ev_eval_3m", "by_src", "mp_net_less_fees", "mp_passes",
        "mp_bought", "mp_per_eval", "mp_pass_per_eval", "mp_pass_per_month", "max_risk", "med_risk")


def line(o, s):
    x = o[s]
    return (f"{s:7s} 2w {x['p10']:5.1f}/{x['f10']:4.1f}/{x['s10']:4.1f} p15 {x['p15']:5.1f} med {x['pass_med']} "
            f"path {x['net']:+7,} less fees {x['path_net_less_fees']:+7,} ({x['b2b']}) $/eval {x['per_eval']:+5} "
            f"mp {x['mp_net_less_fees']:+7,} mp$/eval {x['mp_per_eval']:+5} pass/eval {x['mp_pass_per_eval']} "
            f"PF {x['pf']} DD {x['dd']:,} tpw {x['tpw']} sig {x['sig_tpw']}/wk wk2 {x['sig_wk2']}%")


def cmd_grid():
    import time
    t0 = time.time()
    F, P = families()
    print(len(F), "variants;", len(P), "gate picks from 2021-24:", flush=True)
    for p in P:
        print("  ", p["member"], p["f"], "out", p["out"], "2021-24 mean R", p["r2124"], "n", p["n2124"])
    R = run(F)
    base = next(o for f, n, V, o in R if f == "base")
    rows = []
    for f, n, V, o in R:
        if "error" in o:
            print("ERROR", n, o["error"], o.get("tb"))
            rows.append({"family": f, "name": n, "V": V, "o": o})
            continue
        v = verdict(o, base, f)
        rows.append({"family": f, "name": n, "V": V, "o": {s: {k: o[s].get(k) for k in KEEP} for s in o}, "verdict": v})
    print(f"scored in {time.time() - t0:.0f}s")
    json.dump({"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "gate_picks": P, "rows": rows}, open(OUT, "w"),
              separators=(",", ":"), default=str)
    report(rows)
    return rows


def report(rows):
    base = next(r for r in rows if r["family"] == "base")
    print("BASE")
    for s in SPANS:
        print("   " + line(base["o"], s))
    for r in rows:
        if r["family"] == "base" or "error" in r["o"]:
            continue
        v = r["verdict"]
        tag = ("PASS" if v["pass"] else "both" if v["both"] else "h1" if v["h1"] else "h2" if v["h2"] else "--") + f" ref{v['ref']}"
        print(f"\n[{r['family']}] {r['name']}  {tag}")
        for s in SPANS:
            print("   " + line(r["o"], s))


# ================================================================================================ placebo
def placebo(V, base_o, n=200, seed=7):
    """Random skips: for each gated member, drop the same NUMBER of that member's trades per span as the gate drops, at
    random. Share of placebos that pass the same v2 rule (and the "both 2026 halves" part alone)."""
    install()
    rng = random.Random(seed)
    g = V["gate"]
    drops = {}
    for nm, gg in g.items():
        U = M.units()[nm]
        cut = [u for u in U if any(lo <= fact(u, gg["f"]) < hi for lo, hi in gg["out"])]
        per = collections.Counter(_span_of(u["day"]) for u in cut)
        drops[nm] = (U, per)
    jobs = []
    for i in range(n):
        dd = {}
        for nm, (U, per) in drops.items():
            ids = []
            for sp, k in per.items():
                pool = [u["entry_t"] for u in U if _span_of(u["day"]) == sp]
                ids += rng.sample(pool, min(k, len(pool)))
            dd[nm] = ids
        W = copy.deepcopy(V)
        W.pop("gate")
        W["drop"] = dd
        jobs.append(("placebo", f"p{i}", W))
    R = run(jobs)
    ok = [o for _, _, _, o in R if "error" not in o]
    vs = [verdict(o, base_o) for o in ok]
    return {"n": len(ok), "pass": round(100.0 * sum(v["pass"] for v in vs) / len(vs), 1),
            "both": round(100.0 * sum(v["both"] for v in vs) / len(vs), 1),
            "h2_net_ge": round(100.0 * sum(1 for o in ok if o["H2"]["net"] >= 0) / len(ok), 1)}


def _span_of(d):
    for s in SPANS:
        a, z = M.SPANS[s]
        if a <= d <= z:
            return s
    return "other"


# ================================================================================================ store
W5 = {"SHA": 0.5, "SHT": 0.5}
RUNS = [
    ("atlas_v2_base", "ATLAS today under the real account-B rules (v2 scorer: + money averaged over eval starts, $ per $63 eval)",
     "info", V_()),
    ("atlas_v2_hunts_w05", "ATLAS + both stop-hunt candidates (sh_asia, sh_trend) as members 4 and 5 at half size", "promising",
     V_(members=H5, w=W5)),
    ("atlas_v2_hunts_w05_stuck200", "ATLAS + both stop hunts at half size + buy a new eval under $200 of room (post-hoc stack)",
     "promising", V_(members=H5, w=W5, min_room=200.0)),
    ("atlas_v2_hunts_w075", "ATLAS + both stop-hunt candidates as members 4 and 5 at 0.75 size", "promising",
     V_(members=H5, w={"SHA": 0.75, "SHT": 0.75})),
    ("atlas_v2_ema06_shteve", "ATLAS with no EMA entry in the 06:00 hour + sh_trend in the evening only (18:00-02:00)", "promising",
     V_(members=MEM3 + ["SHT"], gate={**EMA_H6, "SHT": {"f": "hour", "out": [[2, 18]]}})),
    ("atlas_v2_sht_full", "ATLAS + sh_trend at full size (money up in all 4 spans, H1 2-week pass down 5 points)", "rejected",
     V_(members=MEM3 + ["SHT"])),
    ("atlas_v2_sha_full", "ATLAS + sh_asia at full size", "rejected", V_(members=MEM3 + ["SHA"])),
    ("atlas_v2_ema_no06", "ATLAS with no EMA entry in the 06:00 ET hour (gate picked on 2021-24 only)", "rejected", V_(gate=EMA_H6)),
    ("atlas_v2_stuck300", "ATLAS, buy a new eval when the room is under $300 (was $100)", "rejected", V_(min_room=300.0)),
    ("atlas_v2_idle_s15_300", "ATLAS, from session 15 an eval with under $300 room counts as stuck", "rejected", V_(idle=[15, 300.0])),
    ("atlas_v2_cap05", "ATLAS, after session 10 cap at 50% of the room (was 30%)", "rejected", V_(cfg={"two_week_until": 10, "safe_cap": 0.5})),
]


def cmd_save():
    from tools import runlib as rl
    warm()
    Q = ("Owner 2026-10-25: make ATLAS (account B, Builder 25K) stronger: hold in 2026 H1 pick + H2 check AND do not lose in "
         "2025 / 2021-24; eval path as $ per $63 eval")
    sess = [d for d in M.units()["sessions"] if d >= "2021-01-01"]
    for rid, title, status, V in RUNS:
        o, P = score(V, keep_paths=True)
        T = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"],
              "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0, "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"],
              "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": t["src"], "mfe": None, "mae": None,
              "bars_held": None, "regime": "", "mult": None, "low": t["low"]} for s in SPANS for t in P[s]]
        f = lambda s: (f"2-week pass/fail/stuck {o[s]['p10']}/{o[s]['f10']}/{o[s]['s10']} (dec10 {o[s]['dec10']}), p15/f15 "
                       f"{o[s]['p15']}/{o[s]['f15']}, slow_pass {o[s]['slow_pass']}%, pass_med {o[s]['pass_med']}; eval money less fees "
                       f"(mean of starts every 5th session) ${o[s][MONEY]:+,} = ${o[s]['mp_per_eval']:+,} per $63 eval, "
                       f"{o[s]['mp_pass_per_eval']} passes per eval; one-start path {o[s]['net']:+,} (${o[s]['per_month']:,}/mo, PF "
                       f"{o[s]['pf']}, DD {o[s]['dd']:,}); {o[s]['sig_tpw']} candidate trades/wk, {o[s]['sig_wk2']}% weeks 2+")
        rl.save(rid, title, "other", Q, params={"V": V}, sizing={"plan": "builder25k", "size": V.get("size", "need")}, trades=T,
                scored=rl.score(T, sess), status=status,
                verdict=f"Builder 25K. 2026 H1 (pick) {f('H1')}. H2 (check) {f('H2')}. Reference 2025 {f('2025')}; 2021-24 {f('2021-24')}.",
                notes="tools/atlas_v2.py (executor tools/atlas.py + tools/second_account_b.py); stored trades = the one-start "
                      "back-to-back eval path of each span; the run library's own eval columns re-score that path on the 50K plan.",
                writeup="atlas-v2", tags=["second", "account_b", "atlas", "atlas_v2"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "save":
        cmd_save()
        sys.exit(0)
    a = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if a == "units":
        U = install()
        for nm in ("SHA", "SHT", "SHT1"):
            print(nm, len(U[nm]))
    elif a == "grid":
        cmd_grid()
    elif a == "placebo":
        warm()
        d = json.load(open(OUT))
        base = next(r for r in d["rows"] if r["family"] == "base")["o"]
        res = d.get("placebo", {})
        for name in sys.argv[2:]:
            r = next(r for r in d["rows"] if r["name"] == name)
            res[name] = placebo(r["V"], base)
            print(name, res[name], flush=True)
        d["placebo"] = res
        json.dump(d, open(OUT, "w"), separators=(",", ":"), default=str)
    elif a == "plmem":
        warm()
        P = placebo_members(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
        M.units().update(P)
        d = json.load(open(OUT))
        base = next(r for r in d["rows"] if r["family"] == "base")["o"]
        res = {}
        jobs = []
        for lab, mem, w in (("H5w0.5", H5, {"SHA": 0.5, "SHT": 0.5}), ("H5w0.75", H5, {"SHA": 0.75, "SHT": 0.75}),
                            ("SHT", MEM3 + ["SHT"], {}), ("SHA", MEM3 + ["SHA"], {})):
            real = V_(members=mem, w=w)
            jobs.append((lab, "real", real))
            nk = len([k for k in P if k.startswith("PSHA_r")])
            for k in range(nk):
                jobs.append((lab, f"rtime{k}", V_(members=mem, w=w, sub={h: f"P{h}_r{k}" for h in ("SHA", "SHT") if h in mem})))
            jobs.append((lab, "flip", V_(members=mem, w=w, sub={h: f"P{h}_f" for h in ("SHA", "SHT") if h in mem})))
        R = run(jobs)
        for lab in dict.fromkeys(j[0] for j in jobs):
            rr = [(n, o) for f, n, V, o in R if f == lab and "error" not in o]
            real = next(o for n, o in rr if n == "real")
            pl = [o for n, o in rr if n.startswith("rtime")]
            fl = next(o for n, o in rr if n == "flip")
            row = {}
            for s in SPANS:
                row[s] = {"real_p10": real[s]["p10"], "real_dead10": real[s]["dead10"], "real_money": real[s][MONEY],
                          "rtime_p10_mean": round(float(np.mean([o[s]["p10"] for o in pl])), 1),
                          "rtime_dead10_mean": round(float(np.mean([o[s]["dead10"] for o in pl])), 1),
                          "rtime_money_mean": round(float(np.mean([o[s][MONEY] for o in pl]))),
                          "p_p10": round(float(np.mean([o[s]["p10"] >= real[s]["p10"] for o in pl])), 2),
                          "p_money": round(float(np.mean([o[s][MONEY] >= real[s][MONEY] for o in pl])), 2),
                          "flip_p10": fl[s]["p10"], "flip_money": fl[s][MONEY]}
            row["rtime_pass_v2"] = round(100.0 * float(np.mean([verdict(o, base)["pass"] for o in pl])), 1)
            row["n"] = len(pl)
            res[lab] = row
            print(lab, json.dumps(row), flush=True)
        d["placebo_members"] = res
        json.dump(d, open(OUT, "w"), separators=(",", ":"), default=str)
    elif a == "one":
        warm()
        V = V_(**json.loads(sys.argv[2]))
        o = score(V)
        for s in SPANS:
            print(line(o, s))
