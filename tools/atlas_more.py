"""ATLAS more money (2026-11-19, night-atlasmore): more $ for ATLAS on the owner's FUNDED MFFU Builder 25K ($24,887, $887 of room,
first $1,000 payout at about $27,100). Pre-registered design: research/second/atlas_more_design.md (committed before any run).

RESEARCH ONLY. Nothing here touches second_model.json, data/account_b.json, live_model*.json or any engine file.

  python -X utf8 tools/atlas_more.py fresh      # re-run the members (+ the two hunts) on the new bars Oct 19 - Nov 19 (engine/second.run)
  python -X utf8 tools/atlas_more.py diag       # each member per span (+ fresh), the armed-setup block's cost (report only)
  python -X utf8 tools/atlas_more.py ideas      # the 10 ideas (14 variants) on the funded 25K -> research/second/atlas_more.json
  python -X utf8 tools/atlas_more.py control    # random controls for the state / calendar ideas that pass G1-G8
  python -X utf8 tools/atlas_more.py register   # ZEUS Lab rows (kind atlas_more)
  python -X utf8 tools/atlas_more.py all

Scoring is tools/atlas_health.py's (the same trades, the same 600 Monte Carlo paths of 5-session blocks = a week-block
bootstrap, the MFFU Builder 25K funded rules, the live funded preset size, the live $100 stuck stop, today's account, the
real day order, the fixed $250 view). New here: a stuck line / inactivity rule, thin-room member sit-outs, the hunts as
funded members, a tier-1 news exit, a paired week-block bootstrap of each idea vs today, and a fresh 5-week check.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import os
import random
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from tools import atlas as A  # noqa: E402
from tools import atlas_health as AH  # noqa: E402
from tools import atlas_revive as RV  # noqa: E402
from tools import second_mix as M  # noqa: E402

ET = ZoneInfo("America/New_York")
DATE = "2026-11-19"
OUT = os.path.join(ROOT, "research", "second", "atlas_more.json")
OUT_FRESH = os.path.join(ROOT, "research", "second", "atlas_more_fresh.json")
OUT_DIAG = os.path.join(ROOT, "research", "second", "atlas_more_diag.json")
CBOE = os.path.join(ROOT, "research", "runs", "_cache", "edge", "VIX_History.csv")      # gitignored, CBOE's free daily file
CBOE_VXN = os.path.join(ROOT, "research", "runs", "_cache", "edge", "VXN_History.csv")
FRESH = ("2026-10-19", "2026-11-19")
PV, COMM, SLIP = 2.0, 1.90, 0.25
BASE_STUCK = 100.0
IDLE_N = 5                      # sessions without a trade while under $100 of room = MFFU's 7-day inactivity close
FIX = AH.FIX
MEMBERS = ("EMA", "MD", "SR")
LABEL = {"EMA": "EMA (London EMA pullback)", "MD": "MACD (divergence at a sweep)", "SR": "S/R (NY level reclaim)",
         "SHA": "Asia resweep hunt", "SHT": "Trend inducement hunt"}

# ================================================================================================ the pre-registered ideas
IDEAS = {
    "today": {"fam": "base"},
    "A1_stuck_off": {"fam": "A", "stuck": 0.0},
    "A2_stuck_50": {"fam": "A", "stuck": 50.0},
    "A3_thin_macd": {"fam": "A", "thin": 500.0, "thin_keep": ["MD"]},
    "A3_thin_macd_300": {"fam": "A", "thin": 300.0, "thin_keep": ["MD"], "neighbour": "A3_thin_macd"},
    "A3_thin_macd_700": {"fam": "A", "thin": 700.0, "thin_keep": ["MD"], "neighbour": "A3_thin_macd"},
    "A4_thin_no_ema": {"fam": "A", "thin": 500.0, "thin_keep": ["MD", "SR"]},
    "A4_thin_no_ema_300": {"fam": "A", "thin": 300.0, "thin_keep": ["MD", "SR"], "neighbour": "A4_thin_no_ema"},
    "A4_thin_no_ema_700": {"fam": "A", "thin": 700.0, "thin_keep": ["MD", "SR"], "neighbour": "A4_thin_no_ema"},
    "A5_stuck_off_room40": {"fam": "A", "stuck": 0.0, "pct": 0.4},
    "B1_v2_hunts": {"fam": "B", "members": ["EMA", "MD", "SR", "SHA", "SHT"], "w": {"SHA": 0.5, "SHT": 0.5}, "re_measure": True},
    "B2_v2_full": {"fam": "B", "members": ["EMA", "MD", "SR", "SHA", "SHT"], "w": {"SHA": 0.5, "SHT": 0.5}, "stuck": 200.0},
    "B3_asia_hunt": {"fam": "B", "members": ["EMA", "MD", "SR", "SHA"], "w": {"SHA": 0.5}, "re_measure": True},
    "C1_news_flat": {"fam": "C", "news": "all"},
    "C2_news_flat_notbe": {"fam": "C", "news": "notbe"},
}
TEN = [k for k, v in IDEAS.items() if k != "today" and not v.get("neighbour")]
TIMING = {"A3_thin_macd", "A4_thin_no_ema", "C1_news_flat", "C2_news_flat_notbe"}


# ================================================================================================ trades per idea
_C = {}


def sessions():
    return AH.sessions()


def to_T(units, w=None):
    """account units (after one_pos) -> the atlas_health trade format (+ weight)."""
    out = []
    for u in units:
        out.append({"day": u["day"], "entry_t": int(u["entry_t"]), "exit_t": int(u["exit_t"]), "dir": int(u["dir"]),
                    "risk": float(u["risk"]), "tgt": float(u["tgt"] or 0) or None, "pts": float(u["pts"]),
                    "w1": float(min(0.0, u["w1"])), "src": u["src"], "exit": str(u.get("exit", "?")), "R": float(RV.r_net(u)),
                    "strat": "ATLAS", "w": float((w or {}).get(u["src"], 1.0))})
    return sorted(out, key=lambda t: t["entry_t"])


def base_units():
    if "U" not in _C:
        _C["U"] = A.account_units(A.BASE)
    return _C["U"]


def _bars():
    if "B" not in _C:
        from tools import lit_final as F
        Mk, _ = F.market("cisd", [])
        _C["B"] = (F.bars(Mk, "5m"), F.bars(Mk, "1m"))
    return _C["B"]


def tier1_ts():
    """[unix ts] of the tier-1 releases (tools/lit_mffu_rapid_stack.tier1: CPI, jobs report, FOMC 14:00 + 14:30, minutes)."""
    if "N" not in _C:
        from tools import lit_mffu_rapid_stack as RS
        cal = RS.tier1()
        ts = []
        for d, mins in cal.items():
            if d.startswith("_"):
                continue
            for m in mins:
                ts.append(int(dt.datetime.combine(dt.date.fromisoformat(d), dt.time(m // 60, m % 60), ET).timestamp()))
        _C["N"] = sorted(ts)
    return _C["N"]


def news_mod(U, mode, rel=None):
    """C1 / C2: no entry in [release - 5 min, release + 2.5 min); a trade open 3 min before a release is closed at the open
    of the last path bar starting at or before release - 180 s (1 tick slippage), unless mode 'notbe' and it already
    reached +1R. rel = the release times (a shifted calendar for the control)."""
    rel = np.asarray(tier1_ts() if rel is None else rel, np.int64)
    B5, B1 = _bars()
    out, n_block, n_cut = [], 0, 0
    for u in U:
        e0 = int(u["entry_t"])
        k = int(np.searchsorted(rel, e0 - 150, side="left"))
        if k < len(rel) and rel[k] - 300 <= e0 < rel[k] + 150:
            n_block += 1
            continue
        j = int(np.searchsorted(rel, e0 + 180, side="right"))        # the first release at least 3 min after the entry
        cut = None
        while j < len(rel) and rel[j] - 180 < int(u["exit_t"]):
            pt = np.asarray(u.get("pt", []), np.int64)
            ii = int(np.searchsorted(pt, rel[j] - 180, side="right")) - 1
            if ii >= 0 and pt[ii] > e0 and pt[ii] < int(u["exit_t"]):
                cut = (rel[j], ii)
            break
        if cut is None:
            out.append(u)
            continue
        r_t, ii = cut
        pt, po, pw = u["pt"], u["po"], u["pw"]
        if mode == "notbe":
            B = B1 if int(u["entry_t"]) >= int(B1.t[0]) + 86400 else B5
            dr = int(u["dir"])
            k0 = int(np.searchsorted(B.t, int(pt[0])))
            e_dr = float(B.o[k0]) * dr - float(po[0])                 # entry price x dir (po = open - entry, dir space)
            ke = int(np.searchsorted(B.t, e0, side="right")) - 1     # the entry bar
            kc = int(np.searchsorted(B.t, int(pt[ii])))
            hi = B.h if dr == 1 else -B.l
            best = float(np.max(hi[ke:kc]) - e_dr) if kc > ke else 0.0
            if best >= float(u["risk"]):
                out.append(u)
                continue
        n_cut += 1
        pts = float(po[ii]) - SLIP
        w1 = float(max(-(float(u["risk"]) + SLIP), min(0.0, float(pw[ii]), pts)))
        out.append({**u, "pts": round(pts, 4), "w1": round(w1, 4), "exit_t": int(pt[ii]), "exit": "NEWS"})
    return out, {"blocked": n_block, "cut": n_cut}


def idea_T(I, rel=None):
    """The idea's trade list (atlas_health format with weights) + notes."""
    key = json.dumps({k: I.get(k) for k in ("members", "w", "news")}, sort_keys=True) + ("" if rel is None else str(hash(tuple(rel))))
    if key in _C:
        return _C[key]
    note = {}
    if I.get("members"):
        from tools import atlas_v2 as V2
        V2.install()
        U = A.account_units({**A.BASE, "members": list(I["members"])})
    else:
        U = base_units()
    if I.get("news"):
        U, note = news_mod(U, I["news"], rel)
    T = to_T(RV.one_pos(U), I.get("w"))
    _C[key] = (T, note)
    return T, note


# ================================================================================================ the funded 25K with the new rules
def _pgf():
    import builder_levers as BL
    from engine import sizing as SZ
    from tools import uprisk as U

    class PGF2(BL.GF):
        """tools/atlas_health PGF (funded 25K preset + the live stuck stop) with this study's knobs: stuck (the stuck line),
        the inactivity close under $100 of room, thin (room under $X: only thin_keep members), pct (share of the room),
        thin_p (control: under $X skip each signal with probability p, seeded)."""

        def __init__(self, I):
            super().__init__("builder25k", U.UP25, {"ATLAS": ("fq", None)})
            self.I = I
            self.stuck_at = float(I.get("stuck", BASE_STUCK))
            self.dead, self.min_room = None, float(self.A["mll"])
            self.idle, self.n_skip_thin, self.n_last = 0, 0, 0
            self.rng = random.Random(I.get("seed", 0)) if I.get("thin_p") is not None else None

        def qty(self, t, st):
            I = self.I
            if self.dead:
                return 0
            if st["room"] < self.stuck_at:
                self.dead = "stuck"
                return 0
            w = float(t.get("w", 1.0))
            if w <= 0:
                return 0
            if I.get("thin") and st["room"] < float(I["thin"]):
                if I.get("thin_p") is not None:
                    if self.rng.random() < float(I["thin_p"]):
                        self.n_skip_thin += 1
                        return 0
                elif t["src"] not in I["thin_keep"]:
                    self.n_skip_thin += 1
                    return 0
            c = self.cfg
            if I.get("pct") is not None:
                c = {**c, "pct": float(I["pct"])}
            tt = t if t.get("tgt") else {**t, "tgt": 2.0 * t["risk"]}
            q = SZ.funded_qty({**tt, "tgt_pts": tt["tgt"], "risk_pts": tt["risk"]}, st, c, acct=self.A)
            if q > 0 and w != 1.0:
                q = min(q, max(1, int(q * w + 1e-9)))
            return max(0, int(q))

        def step(self, ts, keep=None):
            n0 = self.n_tr
            ev, x = super().step(ts, keep)
            if self.state == "on":
                st0, _ = self._fast_state()
                room = st0["balance"] - st0["floor"]
                self.min_room = min(self.min_room, room)
                if self.stuck_at < BASE_STUCK and room < BASE_STUCK and not self.dead:
                    self.idle = 0 if self.n_tr > n0 else self.idle + 1
                    if self.idle >= IDLE_N:
                        self.dead = "idle"
                else:
                    self.idle = 0
            return ev, x
    return PGF2


def at_today(f):
    AH.at_today(f)
    return f


def run_paths(BY, paths, mk, real=False):
    """atlas_health.run_paths + the per-path $ a month (for the paired bootstrap) and the idle deaths."""
    from tools import uprisk as U
    LEN = U.LEN
    rows = []
    for seq in paths:
        f = mk()
        owner, first, npay, end = 0.0, None, 0, "on"
        seq = list(seq[:LEN])
        for k, si in enumerate(seq):
            ev, x = f.step(BY[si])
            if ev in ("paid", "grad"):
                owner += x
                npay += 1
                first = first or k + 1
            if ev == "lost":
                end = "lost"
                break
            if ev == "grad":
                end = "grad"
                break
            if f.dead:
                end = f.dead
                break
        months = (len(seq) if real else LEN) / 21.0
        rows.append((owner / months, first, npay, end, f.min_room, f.n_skip_thin))
    n = len(rows)
    fr = [r[1] for r in rows if r[1]]
    return {"per_month": round(float(np.mean([r[0] for r in rows]))), "first_med": float(np.median(fr)) if fr else None,
            "no_pay_6m": round(100.0 * (n - len(fr)) / n, 1), "lost_6m": round(100.0 * sum(r[3] == "lost" for r in rows) / n, 1),
            "stuck_6m": round(100.0 * sum(r[3] == "stuck" for r in rows) / n, 1),
            "idle_6m": round(100.0 * sum(r[3] == "idle" for r in rows) / n, 1),
            "dead_6m": round(100.0 * sum(r[3] in ("lost", "stuck", "idle") for r in rows) / n, 1),
            "payouts": round(float(np.mean([r[2] for r in rows])), 2), "thin_skips": round(float(np.mean([r[5] for r in rows])), 2),
            "paths": n, "_pm": [round(r[0], 2) for r in rows], "_end": [r[3] for r in rows], "_first": [r[1] for r in rows]}


def score(I, T, S, PF, RS, quick=False):
    import builder_levers as BL
    PGF = _pgf()
    BY = RV.by_session(T, S)
    row = {"fixed": AH.fixed_view(T, S, {})[0]}
    row["funded"] = {sp: run_paths(BY, PF[sp], lambda: PGF(I)) for sp in BL.SPANS}
    row["today_state"] = {sp: run_paths(BY, PF[sp], lambda: at_today(PGF(I))) for sp in BL.SPANS}
    if not quick:
        row["real"] = {sp: run_paths(BY, RS[sp], lambda: PGF(I), real=True) for sp in BL.SPANS}
    return row


def boot(a, b, n=2000, seed=11):
    """Paired week-block bootstrap: the paths are already 5-session-block resamples; resample the paired per-path
    differences n times -> mean, 5th / 95th percentile of the mean, share of paths where the idea pays more / less."""
    d = np.asarray(a, float) - np.asarray(b, float)
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), size=(n, len(d)))].mean(axis=1)
    up, dn = int((d > 0.5).sum()), int((d < -0.5).sum())
    p_sign = float(sum(math.comb(up + dn, k) for k in range(up, up + dn + 1)) / 2 ** (up + dn)) if up + dn else 1.0
    return {"mean": round(float(d.mean()), 1), "p5": round(float(np.percentile(m, 5)), 1), "p95": round(float(np.percentile(m, 95)), 1),
            "paths_more": round(100 * float((d > 0.5).mean()), 1), "paths_less": round(100 * float((d < -0.5).mean()), 1),
            "n_more": up, "n_less": dn, "p_sign": round(p_sign, 6)}


def zombie(r, b):
    """The paths where today's rule strands the account (stuck under $100): what the idea does with them instead."""
    out = {}
    for lab in ("funded", "today_state"):
        out[lab] = {}
        for sp in r[lab]:
            be, ie, bf, if_, bp, ip = b[lab][sp]["_end"], r[lab][sp]["_end"], b[lab][sp]["_first"], r[lab][sp]["_first"], b[lab][sp]["_pm"], r[lab][sp]["_pm"]
            ks = [k for k, e in enumerate(be) if e == "stuck"]
            n = len(be)
            out[lab][sp] = {"stuck_today_pct": round(100 * len(ks) / n, 1),
                            "of_them_paid_later_pct": round(100 * sum(1 for k in ks if (if_[k] or 0) and not bf[k]) / max(1, len(ks)), 1),
                            "of_them_more_usd_pct": round(100 * sum(1 for k in ks if ip[k] > bp[k] + 0.5) / max(1, len(ks)), 1),
                            "of_them_idle_dead_pct": round(100 * sum(1 for k in ks if ie[k] == "idle") / max(1, len(ks)), 1),
                            "of_them_alive_pct": round(100 * sum(1 for k in ks if ie[k] in ("on", "grad")) / max(1, len(ks)), 1),
                            "usd_month_gain_all_paths": round(float(np.mean(ip) - np.mean(bp)), 1)}
    return out


def gate(r, b, I):
    """G1-G8 + G10 of research/second/atlas_more_design.md. -> (ok, [why not])."""
    why = []
    for lab, f, fb in (("fresh", r["funded"], b["funded"]), ("today's acct", r["today_state"], b["today_state"])):
        for sp in ("H1", "H2"):
            if f[sp]["per_month"] < fb[sp]["per_month"] - 10:
                why.append(f"G1 {lab} {sp} ${fb[sp]['per_month']} -> ${f[sp]['per_month']}/mo")
        if f["REF"]["per_month"] < fb["REF"]["per_month"] - 5:
            why.append(f"G1 {lab} 2021-25 ${fb['REF']['per_month']} -> ${f['REF']['per_month']}/mo")
        for sp in ("H1", "H2", "REF"):
            for k in ("dead_6m", "no_pay_6m"):
                if f[sp][k] > fb[sp][k] + 0.5:
                    why.append(f"G3 {lab} {sp} {k.split('_')[0]} {fb[sp][k]} -> {f[sp][k]}%")
        for sp in ("H1", "H2"):
            if (f[sp]["first_med"] or 999) > (fb[sp]["first_med"] or 999) + 1:
                why.append(f"G4 {lab} {sp} 1st payout {fb[sp]['first_med']} -> {f[sp]['first_med']} sessions")
    t, tb = r["today_state"], b["today_state"]
    gain = all(t[sp]["per_month"] >= tb[sp]["per_month"] + 10 for sp in ("H1", "H2"))
    safer = any(t[sp]["dead_6m"] <= tb[sp]["dead_6m"] - 1.0 for sp in ("H1", "H2")) and \
        not any(t[sp]["dead_6m"] > tb[sp]["dead_6m"] for sp in ("H1", "H2", "REF"))
    if not (gain or safer):
        why.append("G2 no real gain (+$10/mo in both halves) and not safer (-1 point dead) from today's account")
    for sp in ("H1", "H2"):
        tp = r["fixed"][sp]["tpw"]
        if not 2.0 <= tp <= 4.1:
            why.append(f"G5 {sp} {tp} trades a week")
    q, qb = r["real"], b["real"]
    for sp in ("H1", "H2", "REF"):
        if q[sp]["dead_6m"] > qb[sp]["dead_6m"]:
            why.append(f"G6 real order {sp} dead {qb[sp]['dead_6m']} -> {q[sp]['dead_6m']}%")
    for sp in ("H1", "H2"):
        if q[sp]["per_month"] < qb[sp]["per_month"] - 10:
            why.append(f"G6 real order {sp} ${qb[sp]['per_month']} -> ${q[sp]['per_month']}/mo")
    if I["fam"] in ("B", "C"):
        x, xb = r["fixed"], b["fixed"]
        for sp in ("H1", "H2"):
            if x[sp]["net"] < xb[sp]["net"]:
                why.append(f"G7 fixed $250 {sp} net ${xb[sp]['net']:,} -> ${x[sp]['net']:,}")
        if x["2025"]["net"] + x["2021-24"]["net"] < xb["2025"]["net"] + xb["2021-24"]["net"]:
            why.append(f"G7 fixed $250 2021-25 net ${xb['2025']['net'] + xb['2021-24']['net']:,} -> ${x['2025']['net'] + x['2021-24']['net']:,}")
    if not r.get("acts_h2"):
        why.append("G8 never acts in Jul-Oct")
    for sp in ("H1", "H2"):
        if r["boot_today"][sp]["p5"] < -10:
            why.append(f"G10 bootstrap {sp} 90% interval low end {r['boot_today'][sp]['p5']:+} $/mo (< -$10)")
    return (not why), why


def strip(row):
    """Drop the per-path arrays before saving."""
    out = {}
    for k, v in row.items():
        if isinstance(v, dict):
            out[k] = {sp: ({kk: vv for kk, vv in x.items() if not kk.startswith("_")} if isinstance(x, dict) else x) for sp, x in v.items()}
        else:
            out[k] = v
    return out


def cmd_ideas(n=600, log=print):
    import builder_levers as BL
    from tools import uprisk as U
    from tools import zeus_lab as Z
    t0 = time.time()
    S = sessions()
    PF = {sp: U.mc_paths(S, sp, n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    RS = AH.real_starts(S)
    T0, _ = idea_T(IDEAS["today"])
    chk = AH.stream()
    assert [(t["entry_t"], round(t["pts"], 3)) for t in T0] == [(t["entry_t"], round(t["pts"], 3)) for t in chk], "base != atlas_health"
    out = {"date": DATE, "n": n, "spans": U.SPAN, "fixed_spans": FIX, "design": "research/second/atlas_more_design.md",
           "today_balance": AH.TODAY_BAL, "rows": {}}
    base = None
    p0 = None
    for nm, I in IDEAS.items():
        T, note = idea_T(I)
        r = score(I, T, S, PF, RS)
        r["idea"], r["fam"], r["note"] = {k: v for k, v in I.items()}, I["fam"], note
        if base is None:
            base = r
            _, p0 = AH.fixed_view(T, S, {})
        # per-trade fixed-$250 deltas in 2026 (Lab sign-flip) + does it act in Jul-Oct
        _, p1 = AH.fixed_view(T, S, {})
        D = []
        for k in set(p0) | set(p1):
            dlt = p1.get(k, 0.0) - p0.get(k, 0.0)
            if abs(dlt) > 0.5:
                day = dt.datetime.fromtimestamp(int(k), ET).date().isoformat()
                if day >= "2026-01-01":
                    D.append({"day": day, "t": str(k), "usd": round(dlt, 2)})
        r["deltas_2026"] = sorted(D, key=lambda x: x["t"])
        r["flip"] = {sp: Z.signflip_p([d["usd"] for d in D if Z.span_of(d["day"], "atlas") == sp]) for sp in ("H1", "H2")}
        r["acts_h2"] = bool(any("2026-07-01" <= d["day"] <= "2026-10-16" for d in D) or
                            any({k: v for k, v in r[x]["H2"].items() if not k.startswith("_")} != {k: v for k, v in base[x]["H2"].items() if not k.startswith("_")}
                                for x in ("funded", "today_state")))
        if nm in ("A1_stuck_off", "A2_stuck_50", "A5_stuck_off_room40"):
            r["zombie"] = zombie(r, base)
        r["boot_today"] = {sp: boot(r["today_state"][sp]["_pm"], base["today_state"][sp]["_pm"]) for sp in BL.SPANS}
        r["boot_fresh"] = {sp: boot(r["funded"][sp]["_pm"], base["funded"][sp]["_pm"]) for sp in BL.SPANS}
        if I["fam"] == "A":            # funded-only rules change no trade: the Lab's luck test = a paired sign test over the paths
            r["flip"] = {sp: r["boot_today"][sp]["p_sign"] for sp in ("H1", "H2")}
        if nm == "today":
            ok, why = None, []
        else:
            ok, why = gate(r, base, I)
        r["gate_ok"], r["gate_why"] = ok, why
        r["kind"] = "base" if nm == "today" else ("neighbour" if I.get("neighbour") else ("re-measure" if I.get("re_measure") else "pre-declared"))
        out["rows"][nm] = strip(r)
        f, x, td = r["funded"], r["fixed"], r["today_state"]
        log(f"{nm:22s} fresh " + " | ".join(f"{sp} ${f[sp]['per_month']} 1st {f[sp]['first_med']} np {f[sp]['no_pay_6m']} dead {f[sp]['dead_6m']}"
                                            for sp in BL.SPANS) + f"  [{time.time() - t0:.0f}s]")
        log(f"{'':22s} today " + " | ".join(f"{sp} ${td[sp]['per_month']} 1st {td[sp]['first_med']} np {td[sp]['no_pay_6m']} dead {td[sp]['dead_6m']}"
                                            f" boot {r['boot_today'][sp]['p5']:+}..{r['boot_today'][sp]['p95']:+}" for sp in BL.SPANS))
        log(f"{'':22s} fixed " + " | ".join(f"{sp} {x[sp]['tpw']}/wk PF {x[sp]['pf']} ${x[sp]['net']:,} ${x[sp]['per_month']}/mo dd {x[sp]['max_dd']}"
                                            for sp in FIX) + (f"  note {note}" if note else ""))
        if ok is not None:
            log(f"{'':22s} {'PASS (G1-G8, G10)' if ok else 'no: ' + '; '.join(why)[:400]}")
        if r.get("zombie"):
            log(f"{'':22s} zombie (today's acct): {json.dumps(r['zombie']['today_state'])}")
    out["passers"] = [nm for nm, r in out["rows"].items() if r.get("gate_ok")]
    out["ten"] = TEN
    out["variants"] = len(IDEAS) - 1
    out["took_s"] = round(time.time() - t0)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    log(f"passers (G1-G8, G10): {out['passers']}  wrote {os.path.relpath(OUT, ROOT)} in {out['took_s']}s")
    return out


def cmd_control(draws=40, n=300, log=print):
    """G9: for each timing / state idea (A3, A4, C1, C2) that passed G1-G8 + G10. A3 / A4: under the same room line, skip
    each signal with the probability that the rule skips (the share of non-kept members' trades), seeded. C1 / C2: every
    release moved to a random other weekday of its span (same clock time). Hit = a draw as good on H1 + H2 money (from
    today's account) and no more dead accounts in any span. Needs <= 10% hits."""
    import builder_levers as BL
    from tools import uprisk as U
    o = json.load(open(OUT, encoding="utf-8"))
    todo = [nm for nm in o["passers"] if nm in TIMING]
    if not todo:
        log("no timing / state idea passed G1-G8 + G10: no control to run")
        o["control"] = {"ran": False, "why": "no timing / state idea passed G1-G8 + G10"}
        json.dump(o, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
        return o
    S = sessions()
    PF = {sp: U.mc_paths(S, sp, n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    PGF = _pgf()
    res = {}
    for nm in todo:
        I = IDEAS[nm]
        T, _ = idea_T(I)
        BY = RV.by_session(T, S)
        mine = {sp: run_paths(BY, PF[sp], lambda: at_today(PGF(I))) for sp in BL.SPANS}
        hits, D = 0, []
        rng = random.Random(20261119)
        for k in range(draws):
            if I["fam"] == "A":
                T0, _ = idea_T(IDEAS["today"])
                share = float(np.mean([t["src"] not in I["thin_keep"] for t in T0]))
                J = {**I, "thin_p": share, "seed": 1000 + k}
                g = {sp: run_paths(BY, PF[sp], lambda: at_today(PGF(J))) for sp in BL.SPANS}
            else:
                rel = shifted_calendar(rng, S)
                T2, _ = idea_T(I, rel=rel)
                g = {sp: run_paths(RV.by_session(T2, S), PF[sp], lambda: at_today(PGF(I))) for sp in BL.SPANS}
            good = all(g[sp]["per_month"] >= mine[sp]["per_month"] for sp in ("H1", "H2")) and \
                all(g[sp]["dead_6m"] <= mine[sp]["dead_6m"] for sp in BL.SPANS)
            hits += int(good)
            D.append({sp: {"per_month": g[sp]["per_month"], "dead_6m": g[sp]["dead_6m"]} for sp in BL.SPANS})
        res[nm] = {"hits": hits, "draws": draws, "ok": hits / draws <= 0.1,
                   "rule": {sp: {"per_month": mine[sp]["per_month"], "dead_6m": mine[sp]["dead_6m"]} for sp in BL.SPANS},
                   "draws_median": {sp: {k: float(np.median([d[sp][k] for d in D])) for k in ("per_month", "dead_6m")} for sp in BL.SPANS}}
        log(f"{nm}: control draws as good {hits}/{draws} -> {'ok' if res[nm]['ok'] else 'NOT better than random'}; rule {res[nm]['rule']} "
            f"random median {res[nm]['draws_median']}")
    o["control"] = {"ran": True, "rows": res, "n_paths": n}
    for nm, r in res.items():
        if not r["ok"]:
            o["rows"][nm]["gate_ok"] = False
            o["rows"][nm]["gate_why"].append(f"G9 random control as good in {r['hits']}/{r['draws']} draws")
    o["passers"] = [nm for nm, r in o["rows"].items() if r.get("gate_ok")]
    json.dump(o, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    return o


def shifted_calendar(rng, S):
    """Each tier-1 release moved to a random other weekday session of its span (same clock time)."""
    from tools import uprisk as U
    out = []
    spans = {sp: [d for d in S if a <= d <= z] for sp, (a, z) in U.SPAN.items()}
    for ts in tier1_ts():
        x = dt.datetime.fromtimestamp(int(ts), ET)
        d = x.date().isoformat()
        sp = next((k for k, v in spans.items() if v and v[0] <= d <= v[-1]), None)
        if sp is None:
            continue
        nd = rng.choice(spans[sp])
        out.append(int(dt.datetime.combine(dt.date.fromisoformat(nd), x.time(), ET).timestamp()))
    return sorted(out)


# ================================================================================================ fresh 5 weeks (Oct 19 - Nov 19)
FRESH_KEYS = {"ema_lon_vix": "EMA", "macd_sweep": "MD", "sr_nyreclaim": "SR", "sh_asia": "SHA", "sh_trend": "SHT"}


def _vix_patch():
    """pd.read_csv of data/VIX_1d.csv / VXN_1d.csv -> + CBOE's daily closes after the file's last day (the PC's
    engine/news.py does the same refresh live). Returns the undo function."""
    import pandas as pd
    orig = pd.read_csv

    def ext(path, cboe):
        v = orig(path)
        if not os.path.exists(cboe):
            return v
        c = orig(cboe)
        c.columns = [x.lower() for x in c.columns]
        c["date"] = pd.to_datetime(c["date"], format="%m/%d/%Y").dt.strftime("%Y-%m-%d")
        c = c[c["date"] > str(v["date"].max())]
        cols = [x for x in v.columns if x in c.columns]
        return pd.concat([v, c[cols]], ignore_index=True)

    def rc(path, *a, **kw):
        p = str(path)
        if not a and not kw:
            if p.endswith(os.path.join("data", "VIX_1d.csv")):
                return ext(p, CBOE)
            if p.endswith(os.path.join("data", "VXN_1d.csv")):
                return ext(p, CBOE_VXN)
        return orig(path, *a, **kw)
    pd.read_csv = rc
    from engine import lit
    tmp = os.path.join(ROOT, "research", "runs", "_cache", "edge", "VIX_1d_ext.csv")
    ext(os.path.join(ROOT, "data", "VIX_1d.csv"), CBOE).to_csv(tmp, index=False)
    old = dict(lit.VOL_SRC)
    lit.VOL_SRC["VIX"] = tmp

    def undo():
        pd.read_csv = orig
        lit.VOL_SRC.clear()
        lit.VOL_SRC.update(old)
    return undo


def cmd_fresh(log=print):
    """engine/second.run (the live paper code) cut at 17:00 ET of every new session Oct 19 - Nov 19, the members + the
    two hunts. Each trade is taken from the poll of its own day (finished trades only)."""
    import pandas as pd
    from engine import second
    from engine.data import load, load_ltf
    t0 = time.time()
    undo = _vix_patch()
    try:
        df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        cut0 = int(dt.datetime.combine(dt.date.fromisoformat("2026-08-01"), dt.time(0, 0), ET).timestamp())
        df5 = df5[df5["time"] >= cut0].reset_index(drop=True)
        b1, _ = load_ltf("NQ", load("NQ", "5m"))
        b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
        T5 = df5["time"].values
        cfg = second.load_cfg()
        cfg = {**cfg, "strategies": {k: {**v, "on": True} for k, v in cfg["strategies"].items() if k in FRESH_KEYS}}
        days = sorted({dt.datetime.fromtimestamp(int(t) + 6 * 3600, ET).date().isoformat() for t in df5["time"]})
        days = [d for d in days if FRESH[0] <= d <= FRESH[1] and dt.date.fromisoformat(d).weekday() < 5]
        got, par = collections.defaultdict(list), collections.defaultdict(list)
        errs = []
        par_days = ["2026-10-07", "2026-10-13", "2026-10-15"]    # parity: stored research trades must come out again
        for d in days + par_days:
            now = int(dt.datetime.combine(dt.date.fromisoformat(d), dt.time(17, 0), ET).timestamp())
            cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
            cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
            r = second.run(cut5, one_min=cut1, now=now, cfg=cfg, lit=[])
            for k, s in r["strategies"].items():
                if s.get("error"):
                    errs.append((d, k, s["error"]))
                for t in s["trades"]:
                    if t["day"] == d and t.get("exit_t"):
                        (got if d in days else par)[k].append(t)
            log(f"  {d}: " + ", ".join(f"{FRESH_KEYS[k]} {sum(1 for t in s['trades'] if t['day'] == d)}" for k, s in r["strategies"].items())
                + f"  [{time.time() - t0:.0f}s]")
    finally:
        undo()
    ref = {"ema_lon_vix": "second/ema_best.json", "macd_sweep": "second/md_best.json", "sr_nyreclaim": "second/sr_best.json",
           "sh_asia": "stophunt/sh_asia_resweep.json", "sh_trend": "stophunt/sh_trend_idm5.json"}
    parity = {}
    for k, f in ref.items():
        R = {(int(t["entry_t"]), int(t["dir"])): t for t in json.load(open(os.path.join(ROOT, "research", f), encoding="utf-8"))["trades"]
             if t["day"] in ("2026-10-07", "2026-10-13", "2026-10-15")}
        G = {(int(t["entry_t"]), int(t["dir"])): t for t in par.get(k, [])}
        parity[FRESH_KEYS[k]] = {"research": len(R), "replay": len(G), "same_entries": len(set(R) & set(G)),
                                 "same_exit": sum(1 for x in set(R) & set(G) if int(R[x]["exit_t"]) == int(G[x]["exit_t"]))}
    out = {"date": DATE, "window": FRESH, "sessions": days, "errors": errs[:10], "parity_oct": parity,
           "vix_source": "CBOE daily VIX / VXN (free file) appended after data/VIX_1d.csv's last day (2026-10-16)",
           "trades": {FRESH_KEYS[k]: v for k, v in got.items()}, "took_s": round(time.time() - t0)}
    json.dump(out, open(OUT_FRESH, "w", encoding="utf-8"), indent=1, default=float)
    log(f"parity (Oct 7 / 13 / 15 vs the stored research trades): {parity}")
    log(f"fresh trades: " + ", ".join(f"{k} {len(v)}" for k, v in out["trades"].items()) + f"; errors {len(errs)}; wrote {os.path.relpath(OUT_FRESH, ROOT)}")
    return out


def fresh_units():
    """The fresh trades -> account-style units (second_mix.second_units on the new bars), by member."""
    o = json.load(open(OUT_FRESH, encoding="utf-8"))
    from tools import atlas_v2 as V2
    U = {}
    for nm, T in o["trades"].items():
        rows = [{**t, "exit_kind": t["exit_kind"]} for t in T]
        U[nm] = [{**u, "src": nm} for u in V2._sh_units(nm, rows)]
    return U


def fresh_view(members, w=None, news=None, usd=250.0):
    """Fresh 5 weeks: the members' trades, one position, max 2 a day (LIT's block not applied), every trade at $250 x w."""
    U = fresh_units()
    L = sorted([u for m in members for u in U.get(m, [])], key=lambda u: u["entry_t"])
    note = {}
    if news:
        L, note = news_mod(L, news, rel=fresh_news())
    T = to_T(RV.one_pos(L), w)
    o = json.load(open(OUT_FRESH, encoding="utf-8"))
    nd = len(o["sessions"])
    p = []
    for t in T:
        loss1 = (t["risk"] + SLIP) * PV + COMM
        q = int(usd * t["w"] // loss1)
        if q > 0:
            p.append(q * (t["pts"] * PV - COMM))
    p = np.array(p, float)
    eq = np.cumsum(p) if len(p) else np.zeros(1)
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    return {"n": len(p), "tpw": round(len(p) / (nd / 5), 2), "pf": round(float(gw / gl), 2) if gl > 0 else None, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (nd / 21)), "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())) if len(p) else 0,
            "sum_r": round(float(sum(t["R"] * t["w"] for t in T)), 2), "note": note}


def fresh_news():
    """Tier-1 releases in the fresh window from data/news/events.csv (the calendar tier1() stops at Oct 16)."""
    import csv
    out = []
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8")):
        ev = r["event"]
        if not (FRESH[0] <= r["date"] <= FRESH[1]):
            continue
        if ("CPI" in ev and "PPI" not in ev) or "Non-Farm Payrolls" in ev or ev.startswith("FOMC") or "minutes" in ev.lower():
            h, mi = map(int, r["time_et"].split(":"))
            out.append(int(dt.datetime.combine(dt.date.fromisoformat(r["date"]), dt.time(h, mi), ET).timestamp()))
    return sorted(out)


# ================================================================================================ diagnostics
def member_stats(T, S, usd=250.0):
    """trades a week / PF / net / $ a month / max DD / R per trade per span at $250 a trade, costs in."""
    out = {}
    for sp, (a, z) in FIX.items():
        days = [d for d in S if a <= d <= z]
        L = [t for t in T if a <= t["day"] <= z]
        p = []
        for t in L:
            loss1 = (t["risk"] + SLIP) * PV + COMM
            q = int(usd // loss1)
            p.append(q * (t["pts"] * PV - COMM))
        p = np.array(p, float)
        eq = np.cumsum(p) if len(p) else np.zeros(1)
        gw, gl = p[p > 0].sum(), -p[p < 0].sum()
        out[sp] = {"n": len(L), "tpw": round(len(L) / (len(days) / 5), 2), "pf": round(float(gw / gl), 2) if gl > 0 else None,
                   "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(days) / 21)),
                   "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())) if len(p) else 0,
                   "avg_r": round(float(np.mean([t["R"] for t in L])), 3) if L else None}
    return out


def cmd_diag(log=print):
    import builder_levers as BL
    from tools import uprisk as U
    S = sessions()
    T0, _ = idea_T(IDEAS["today"])
    out = {"date": DATE, "members_account": {}, "members_own": {}}
    for m in MEMBERS:
        out["members_account"][m] = member_stats([t for t in T0 if t["src"] == m], S)
    Uo = M.units()
    from tools import atlas_v2 as V2
    V2.install()
    for m in MEMBERS + ("SHA", "SHT"):
        out["members_own"][m] = member_stats(to_T(Uo[m]), S)
    out["account"] = member_stats(T0, S)
    for k, v in out["members_account"].items():
        log(f"{k:4s} on the account: " + " | ".join(f"{sp} {x['tpw']}/wk PF {x['pf']} ${x['net']:,} ${x['per_month']}/mo dd {x['max_dd']} {x['avg_r']}R" for sp, x in v.items()))
    for k, v in out["members_own"].items():
        log(f"{k:4s} own ledger: " + " | ".join(f"{sp} {x['tpw']}/wk PF {x['pf']} ${x['net']:,} ${x['per_month']}/mo dd {x['max_dd']} {x['avg_r']}R" for sp, x in v.items()))
    # the armed-setup block's cost (report only: the no-hedge rule is a safety rule)
    Ua = A.account_units({**A.BASE, "armed": False})
    Ta = to_T(RV.one_pos(Ua))
    out["no_armed_block"] = {"fixed": AH.fixed_view(Ta, S, {})[0], "trades_more": {sp: sum(1 for t in Ta if a <= t["day"] <= z) - sum(1 for t in T0 if a <= t["day"] <= z)
                                                                                     for sp, (a, z) in FIX.items()}}
    PF = {sp: U.mc_paths(S, sp, 300, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    PGF = _pgf()
    for lab, T in (("today", T0), ("no_armed_block", Ta)):
        BY = RV.by_session(T, S)
        f = {sp: run_paths(BY, PF[sp], lambda: at_today(PGF({"fam": "base"}))) for sp in BL.SPANS}
        out.setdefault("armed_cost_funded_today", {})[lab] = {sp: {k: v for k, v in x.items() if k != "_pm"} for sp, x in f.items()}
    log(f"armed block: trades more without it {out['no_armed_block']['trades_more']}; funded from today " +
        json.dumps({lab: {sp: x[sp]['per_month'] for sp in x} for lab, x in out['armed_cost_funded_today'].items()}))
    if os.path.exists(OUT_FRESH):
        fr = {m: fresh_view([m]) for m in MEMBERS + ("SHA", "SHT")}
        fr["ATLAS"] = fresh_view(list(MEMBERS))
        fr["ATLAS + hunts x0.5"] = fresh_view(list(MEMBERS) + ["SHA", "SHT"], {"SHA": 0.5, "SHT": 0.5})
        fr["ATLAS + Asia hunt x0.5"] = fresh_view(list(MEMBERS) + ["SHA"], {"SHA": 0.5})
        fr["ATLAS news flat (C1)"] = fresh_view(list(MEMBERS), news="all")
        fr["ATLAS news flat not-BE (C2)"] = fresh_view(list(MEMBERS), news="notbe")
        out["fresh"] = fr
        for k, x in fr.items():
            log(f"fresh {k:28s} {x['n']} trades {x['tpw']}/wk PF {x['pf']} ${x['net']:,} ({x['sum_r']:+}R) dd {x['max_dd']} {x['note'] or ''}")
    json.dump(out, open(OUT_DIAG, "w", encoding="utf-8"), indent=1, default=float)
    log(f"wrote {os.path.relpath(OUT_DIAG, ROOT)}")
    return out


# ================================================================================================ ZEUS Lab
LAB = {
    "A1_stuck_off": ("atlas_more_stuck_off", "ATLAS funded 25K: keep trading 1 micro under $100 of room instead of stopping",
                     "The funded account's stuck stop ($100 of room) is removed: ATLAS keeps trading whenever the live funded size "
                     "still gives 1 micro whose full stop-out fits the room (5 idle sessions under $100 = dead).",
                     "An account the bot gives up on can still climb back on small tight-stop trades."),
    "A2_stuck_50": ("atlas_more_stuck_50", "ATLAS funded 25K: stuck stop at $50 of room instead of $100",
                    "The funded stuck line moves from $100 to $50 of room.", "A lower stuck line keeps the account alive longer."),
    "A3_thin_macd": ("atlas_more_thin_macd", "ATLAS funded 25K: only MACD trades while the room is under $500",
                     "While the funded room is under $500, EMA and S/R signals are skipped; MACD (best R a trade in every span) still trades.",
                     "When the account is thin, only the member with real edge everywhere should risk what is left."),
    "A4_thin_no_ema": ("atlas_more_thin_no_ema", "ATLAS funded 25K: EMA sits out while the room is under $500",
                       "While the funded room is under $500, EMA signals are skipped (MACD + S/R trade).",
                       "EMA has the lowest R a trade in Jan-Jun and ~0 in 2021-25; sitting it out protects a thin account."),
    "A5_stuck_off_room40": ("atlas_more_stuck_off_room40", "ATLAS funded 25K: no stuck stop + 40% of the room a trade",
                            "A1 combined with the open card atlas-funded-room-40 (40% instead of 60% of the room).",
                            "Smaller bets + never giving up = fewer dead accounts at the same money."),
    "B1_v2_hunts": ("atlas_more_v2_hunts", "ATLAS funded 25K: ATLAS v2 = + Asia and trend hunts at half size",
                    "sh_asia + sh_trend join ATLAS on the funded 25K at weight 0.5 (stuck $100).",
                    "More independent trades = more winning days for the payout rules."),
    "B2_v2_full": ("atlas_more_v2_full", "ATLAS funded 25K: ATLAS v2 as built (hunts x0.5 + min_room $200)",
                   "B1 + the built min_room 200 key (stuck at $200 of room).", "The full v2 switch as the account_b keys would apply it."),
    "B3_asia_hunt": ("atlas_more_asia_hunt", "ATLAS funded 25K: + the Asia resweep hunt at half size",
                     "sh_asia joins ATLAS on the funded 25K at weight 0.5 (market entry, 18:00-02:00 ET).",
                     "A second window (Asia) adds trades without crowding the day members."),
    "C1_news_flat": ("atlas_more_news_flat", "ATLAS: flat 3 minutes before CPI / jobs / FOMC, no entry around them",
                     "An open ATLAS trade is closed 3 min before a tier-1 release; no entry from 5 min before to 2.5 min after.",
                     "News spikes stop out trades that would have worked; LIT's old engine closed before high-impact news."),
    "C2_news_flat_notbe": ("atlas_more_news_flat_notbe", "ATLAS: flat before CPI / jobs / FOMC unless already +1R",
                           "C1, but a trade that already reached +1R keeps running.", "Protect only the trades not yet working."),
}


def lab_head(r):
    h = {}
    for sp in ("H1", "H2"):
        x, f = r["fixed"][sp], r["today_state"][sp]
        h[sp] = {"per_month": f["per_month"], "n": x["n"], "tpw": x["tpw"], "pf": x["pf"], "net": x["net"], "dd": x["max_dd"],
                 "first_med": f["first_med"], "no_pay_6m": f["no_pay_6m"], "dead_6m": f["dead_6m"]}
    for sp in ("2025", "2021-24"):
        x = r["fixed"][sp]
        h[sp] = {"per_month": r["today_state"]["REF"]["per_month"], "n": x["n"], "tpw": x["tpw"], "pf": x["pf"], "net": x["net"],
                 "dd": x["max_dd"], "dead_6m": r["today_state"]["REF"]["dead_6m"]}
    return h


def lab_result(e: dict, path: str = OUT) -> dict:
    """ZEUS Lab runner for kind atlas_more: the stored verdict of this tool (research/second/atlas_more.json), the idea
    named by e['family'] (an IDEAS key), funded $ a month from today's account."""
    o = json.load(open(path, encoding="utf-8"))
    rows = o["rows"]
    head0 = lab_head(rows["today"])
    r = rows.get(e.get("family"))
    if r is None:
        return {"proof_ok": False, "why": f"idea {e.get('family')!r} not scored: python -X utf8 tools/atlas_more.py ideas",
                "flip": {}, "head": head0, "base": head0, "deltas": [], "usd_month_by": None}
    h = lab_head(r)
    by = {sp: round(h[sp]["per_month"] - head0[sp]["per_month"]) for sp in ("H1", "H2")}
    ok = bool(r.get("gate_ok"))
    why = "passes the pre-registered gate (research/second/atlas_more_design.md)" if ok else "; ".join(r.get("gate_why") or [])[:300]
    return {"proof_ok": ok, "why": why, "flip": r.get("flip") or {"H1": 1.0, "H2": 1.0}, "head": h, "base": head0,
            "deltas": r.get("deltas_2026") or [], "usd_month_by": by}


def cmd_register(log=print):
    from tools import zeus_lab as Z
    o = json.load(open(OUT, encoding="utf-8"))
    for fam, (eid, title, what, hyp) in LAB.items():
        n_var = 1 + sum(1 for v in IDEAS.values() if v.get("neighbour") == fam)
        e = {"id": eid, "bot": "atlas", "kind": "atlas_more", "family": fam, "cells": n_var, "registered": DATE, "origin": "claude",
             "source": "research/writeups/atlas-more-money-2026-11-19.md (tools/atlas_more.py)", "title": title,
             "what_changes": what, "hypothesis": hyp, "judged_by": "atlas_more",
             "status_note": "passes" if (o["rows"].get(fam) or {}).get("gate_ok") else "rejected"}
        err = Z.register(e, replace=True)
        log(f"{eid}: {'saved' if not err else err}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("fresh", "diag", "ideas", "control", "register", "all"))
    ap.add_argument("--n", type=int, default=600)
    a = ap.parse_args(argv)
    t0 = time.time()
    if a.cmd in ("fresh", "all"):
        cmd_fresh()
    if a.cmd in ("diag", "all"):
        cmd_diag()
    if a.cmd in ("ideas", "all"):
        cmd_ideas(a.n)
    if a.cmd in ("control", "all"):
        cmd_control()
    if a.cmd in ("register", "all"):
        cmd_register()
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
