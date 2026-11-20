"""ATLAS edge (2026-11-20, day-atlasedge): order type, the leg that loses most to slippage, the entry minute, ES legs,
funded-account guards and the payout path, at real fills (6 and 10 ticks a side).
Design (committed before any run): research/second/atlas_edge_design.md. Write-up: research/writeups/atlas-edge-2026-11-20.md.

RESEARCH ONLY. Nothing here touches second_model.json, data/account_b.json, live_model*.json or any engine file.

  python -X utf8 tools/atlas_edge.py run            # A, B, C, E families + the payout path (1,000 paths a market)
  python -X utf8 tools/atlas_edge.py run --n 200    # quick, noisier
  python -X utf8 tools/atlas_edge.py es             # D: the ES legs (needs research/second/atlas_es_trades.json)
  python -X utf8 tools/atlas_edge.py show           # print the stored verdicts
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)

DATE = "2026-11-20"
DESIGN = "research/second/atlas_edge_design.md"
OUT = os.path.join(ROOT, "research", "second", "atlas_edge.json")
TICK = 0.25
PV, COMM, SLIP = 2.0, 1.9, 0.25
JUDGE = (6, 10)
SPANS = ("H1", "H2", "REF")
FXS = ("H1", "H2", "2025", "2021-24")
BASES = {"B60": {"stuck": 0.0}, "B40": {"stuck": 0.0, "pct": 0.4}}
GUARDS = {
    "E1_day_stop": {"daystop": True},
    "E2_streak3_pause3": {"streak_pause": (3, 3)},
    "E3_streak2_1micro": {"streak_shrink": 2},
    "E4_week_cap35": {"week_cap": 0.35},
}
_C = {}


def AF():
    from tools import atlas_fills as m
    return m


def AM():
    return AF()._AM()


def AR():
    from tools import atlas_risk as m
    return m


def bars():
    return AM()._bars()


def has_1m(u):
    _, B1 = bars()
    et_ = int(u["entry_t"])
    if et_ < int(B1.t[0]) + 86400:
        return None
    j = int(np.searchsorted(B1.t, et_))
    return j if j < len(B1.t) and int(B1.t[j]) == et_ else None


# ================================================================================================ unit transforms
def late(u, n, k, tf="1m"):
    """market k bars (1m: k minutes; 5m: k=1 -> the next 5m open) after the 5m open, + n ticks; same stop / target prices;
    None = skipped (stop or target traded before the new entry, or the trade already over); 'untestable' = no 1m bars."""
    B5, B1 = bars()
    if k == 0:
        return AF().priced(u, n, n)
    et_ = int(u["entry_t"])
    if tf == "1m":
        j = has_1m(u)
        if j is None:
            return "untestable"
        B, step = B1, 60
    else:
        j = int(np.searchsorted(B5.t, et_))
        if j >= len(B5.t) or int(B5.t[j]) != et_:
            return None
        B, step = B5, 300
    if j + k >= len(B.t) or int(B.t[j + k]) != et_ + step * k:
        return None
    d = int(u["dir"])
    _, o = AF()._open5(u)
    e_q = o * d + TICK
    s_q = e_q - float(u["risk"])
    t_q = e_q + float(u["tgt"]) if u.get("tgt") else None
    for m in range(k):
        lo_q = float(B.l[j + m]) if d == 1 else -float(B.h[j + m])
        hi_q = float(B.h[j + m]) if d == 1 else -float(B.l[j + m])
        if lo_q <= s_q or (t_q is not None and hi_q >= t_q):
            return None
    if int(u["exit_t"]) <= et_ + step * k:
        return None
    e2 = float(B.o[j + k]) * d + n * TICK
    risk = e2 - s_q
    if risk <= 0.5:
        return None
    x_q = e_q + float(u["pts"]) + (0.0 if AF().is_target(u) else TICK)   # the exit level (stored pts carry 1 tick on a non-target)
    ex = 0.0 if AF().is_target(u) else n * TICK
    pts = x_q - e2 - ex
    w1 = min(0.0, float(u["w1"]) + (e_q - e2), pts)
    w1 = max(w1, -(risk + n * TICK))
    return {**u, "entry_t": et_ + step * k, "risk": round(risk, 4), "tgt": round(t_q - e2, 4) if t_q is not None else u.get("tgt"),
            "pts": round(pts, 4), "w1": round(w1, 4)}


def opt_units(kind, n, spec=None):
    """-> (units, notes). kind: base | limit (x, to) | chase (x, to) | drop (src) | half (src) | late_leg (src, k) |
    c1 ({src: k}) | c2 | c3 ({src: 0|1})."""
    spec = spec or {}
    out, note = [], collections.Counter()
    for u in AF().units():
        src = u["src"]
        if kind == "base":
            out.append(AF().priced(u, n, n))
            continue
        if kind in ("limit", "chase"):
            v = AF().limit_fill(u, spec["x"], n, spec["to"])
            if v is not None:
                note["filled"] += 1
                out.append(v)
                continue
            note["unfilled"] += 1
            note["missed_usd"] += usd250(AF().priced(u, n, n))
            if kind == "chase":
                v = late(u, n, spec["to"], "1m")
                if v == "untestable":
                    v = late(u, n, 1, "5m")
                if isinstance(v, dict):
                    note["chased"] += 1
                    out.append(v)
            continue
        if kind == "drop":
            if src == spec["src"]:
                note["dropped"] += 1
                continue
            out.append(AF().priced(u, n, n))
            continue
        if kind == "half":
            out.append(AF().priced(u, n, n))
            continue
        k, tf = 0, "1m"
        if kind == "late_leg" and src == spec["src"]:
            k = spec["k"]
        elif kind == "c1":
            k = spec.get(src, 0)
        elif kind == "c2":
            k, tf = 1, "5m"
        elif kind == "c3" and spec.get(src):
            k, tf = 1, "5m"
        v = late(u, n, k, tf)
        if v == "untestable":
            note["untestable"] += 1
            v = AF().priced(u, n, n)
        if v is None:
            note["skipped"] += 1
            continue
        out.append(v)
    note = {k: (round(v) if isinstance(v, float) else v) for k, v in note.items()}
    return out, note


def usd250(u):
    q = int(250.0 // ((float(u["risk"]) + SLIP) * PV + COMM))
    return q * (float(u["pts"]) * PV - COMM)


def to_T(U, w=None):
    from tools import atlas_revive as RV
    return AM().to_T(RV.one_pos(U), w)


def fixed(T):
    S = AM().sessions()
    from tools import atlas_health as AH
    return AH.fixed_view(T, S, {})[0]


# ================================================================================================ the funded 25K (today's account)
def pge():
    if "PGE" in _C:
        return _C["PGE"]
    P3 = AR().pgf3()

    class PGE(P3):
        """atlas_risk PGF3 + the guards: daystop, streak_pause (n, sessions), streak_shrink (n), week_cap (share of the room)."""

        def __init__(self, I):
            super().__init__(I)
            self.streak, self.pause_left, self.week, self.week_room0, self.week_pnl = 0, 0, None, 0.0, 0.0

        def qty(self, t, st):
            I = self.I
            if self.pause_left > 0:
                return 0
            if I.get("daystop") and st["cum"] < 0:
                return 0
            if I.get("week_cap") and self.week_pnl + st["cum"] <= -float(I["week_cap"]) * self.week_room0:
                return 0
            q = super().qty(t, st)
            if I.get("streak_shrink") and self.streak >= int(I["streak_shrink"]) and q > 1:
                q = 1
            return q

        def step(self, ts, keep=None):
            wk = self.sess // 5
            if wk != self.week and self.state == "on":
                st0, _ = self._fast_state()
                self.week, self.week_pnl, self.week_room0 = wk, 0.0, max(0.0, st0["balance"] - st0["floor"])
            paused = self.pause_left > 0
            kp = []
            r = super().step(ts, kp)
            if keep is not None:
                keep.extend(kp)
            if paused:
                self.pause_left -= 1
            for _, _, p in kp:
                self.streak = self.streak + 1 if p < 0 else 0
                self.week_pnl += p
            sp = self.I.get("streak_pause")
            if sp and self.streak >= sp[0]:
                self.pause_left, self.streak = sp[1], 0
            return r

    _C["PGE"] = PGE
    return PGE


def funded(I, T, n_paths):
    from tools import atlas_revive as RV
    from tools import uprisk as U
    S, PF = AR().funded_ctx(n_paths)
    BY = RV.by_session(T, S)
    PG = pge()
    cal = AR().calendar()
    out = {}
    for sp in SPANS:
        rows = []
        for seq in PF[sp]:
            f = AM().at_today(PG(I))
            owner, pays, end = 0.0, [], "on"
            for k, si in enumerate(list(seq[:U.LEN])):
                ev, x = f.step(BY[si])
                if ev in ("paid", "grad"):
                    owner += x
                    pays.append(k + 1)
                if ev in ("lost", "grad"):
                    end = ev
                    break
                if f.dead:
                    end = f.dead
                    break
            rows.append((owner / (U.LEN / 21.0), pays, end))
        n = len(rows)

        def med(i):
            arr = np.array([r[1][i] if len(r[1]) > i else 10 ** 6 for r in rows], float)
            m = float(np.percentile(arr, 50, method="lower"))
            return (None, None) if m >= 10 ** 6 else (int(m), cal[int(m) - 1])
        dead = [r for r in rows if r[2] in ("lost", "stuck", "idle")]
        out[sp] = {"usd_m": round(float(np.mean([r[0] for r in rows]))), "first": med(0)[1], "first_k": med(0)[0],
                   "second": med(1)[1], "second_k": med(1)[0],
                   "no_pay_6m": round(100.0 * sum(1 for r in rows if not r[1]) / n, 1),
                   "lost_6m": round(100.0 * len(dead) / n, 1),
                   "lost_before_1st": round(100.0 * sum(1 for r in dead if not r[1]) / n, 1),
                   "payouts": round(float(np.mean([len(r[1]) for r in rows])), 2)}
    return out


def score(T, n_paths, bases=("B60", "B40"), guard=None):
    r = {"fixed": fixed(T)}
    for b in bases:
        I = {**BASES[b], **(guard or {})}
        r[b] = funded(I, T, n_paths)
    return r


# ================================================================================================ gates
def gate_g(opt, base, testable=True):
    why = []
    for n in JUDGE:
        a, b = opt[n], base[n]
        for bb in BASES:
            fa, fb = a[bb], b[bb]
            for sp in ("H1", "H2"):
                if fa[sp]["usd_m"] < fb[sp]["usd_m"] + 10:
                    why.append(f"{n}t {bb} {sp} ${fb[sp]['usd_m']}->${fa[sp]['usd_m']}/mo (needs +$10)")
            if fa["REF"]["usd_m"] < fb["REF"]["usd_m"] - 5:
                why.append(f"{n}t {bb} REF ${fb['REF']['usd_m']}->${fa['REF']['usd_m']}")
            for sp in SPANS:
                if fa[sp]["lost_6m"] > fb[sp]["lost_6m"] + 0.5:
                    why.append(f"{n}t {bb} {sp} lost {fb[sp]['lost_6m']}->{fa[sp]['lost_6m']}%")
        xa, xb = a["fixed"], b["fixed"]
        for sp in ("H1", "H2"):
            if (xa[sp]["pf"] or 0) < (xb[sp]["pf"] or 0):
                why.append(f"{n}t {sp} PF {xb[sp]['pf']}->{xa[sp]['pf']}")
            if not (2.0 <= xa[sp]["tpw"] <= 4.1):
                why.append(f"{n}t {sp} {xa[sp]['tpw']}/wk")
        for sp in FXS:
            if xa[sp]["per_month"] < xb[sp]["per_month"] - 10:
                why.append(f"{n}t {sp} fixed ${xb[sp]['per_month']}->${xa[sp]['per_month']}/mo")
    if not testable:
        why.append("needs 1m bars: 2021-25 untestable")
    return (not why), why


def gate_e(opt, base):
    why = []
    for n in JUDGE:
        for bb in BASES:
            fa, fb = opt[n][bb], base[n][bb]
            for sp in ("H1", "H2"):
                if fa[sp]["lost_6m"] > fb[sp]["lost_6m"] - 0.5:
                    why.append(f"{n}t {bb} {sp} lost {fb[sp]['lost_6m']}->{fa[sp]['lost_6m']}% (needs -0.5)")
                if fa[sp]["usd_m"] < 0.9 * fb[sp]["usd_m"]:
                    why.append(f"{n}t {bb} {sp} ${fb[sp]['usd_m']}->${fa[sp]['usd_m']}/mo (<90%)")
            if fa["REF"]["lost_6m"] > fb["REF"]["lost_6m"] + 0.5:
                why.append(f"{n}t {bb} REF lost {fb['REF']['lost_6m']}->{fa['REF']['lost_6m']}%")
            if fa["REF"]["usd_m"] < fb["REF"]["usd_m"] - 10:
                why.append(f"{n}t {bb} REF ${fb['REF']['usd_m']}->${fa['REF']['usd_m']}")
    return (not why), why


# ================================================================================================ runs
def leg_table():
    """B: each member alone, fixed view at 1 / 6 / 10 ticks."""
    out = {}
    for m in ("EMA", "MD", "SR"):
        out[m] = {}
        for n in (1, 6, 10):
            U = [AF().priced(u, n, n) for u in AF().units() if u["src"] == m]
            out[m][f"{n}t"] = fixed(to_T(U))
    return out


def c1_pick():
    out = {}
    for m in ("EMA", "MD", "SR"):
        best = None
        for k in range(5):
            U = []
            for u in AF().units():
                if u["src"] != m or not ("2026-01-01" <= u["day"] <= "2026-06-30"):
                    continue
                v = late(u, 10, k, "1m")
                if isinstance(v, dict):
                    U.append(v)
            usd = fixed(to_T(U))["H1"]["per_month"]
            if best is None or usd > best[1]:
                best = (k, usd)
        out[m] = {"k": best[0], "h1_per_month": best[1]}
    return out


def c3_pick():
    out = {}
    for m in ("EMA", "MD", "SR"):
        vals = {}
        for k in (0, 1):
            U = []
            for u in AF().units():
                if u["src"] != m or not ("2026-01-01" <= u["day"] <= "2026-06-30"):
                    continue
                v = late(u, 10, k, "5m")
                if isinstance(v, dict):
                    U.append(v)
            vals[k] = fixed(to_T(U))["H1"]["per_month"]
        out[m] = {"late5": int(vals[1] > vals[0]), "h1_per_month": vals}
    return out


def cmd_run(n_paths=1000, log=print):
    t0 = time.time()
    out = {"date": DATE, "design": DESIGN, "n_paths": n_paths, "base": {}, "A": {}, "B": {}, "C": {}, "E": {}}
    base = {}
    for n in (1, 3) + JUDGE:
        base[n] = score(to_T(opt_units("base", n)[0]), n_paths)
        log(f"base {n}t: " + line(base[n]) + f"  [{time.time() - t0:.0f}s]")
    out["base"] = {f"{n}t": v for n, v in base.items()}

    def fam(key, name, kind, spec=None, testable=True, w=None, info=False):
        res, notes = {}, {}
        for n in (3,) + JUDGE:
            U, note = opt_units(kind, n, spec)
            if n == 3:
                res[n] = {"fixed": fixed(to_T(U, w))}
            else:
                res[n] = score(to_T(U, w), n_paths)
            notes[f"{n}t"] = note
        ok, why = gate_g(res, base, testable)
        out[key][name] = {"spec": spec, "kind": kind, "notes": notes, "pass": ok and not info, "why": why,
                          **{f"{n}t": v for n, v in res.items()}}
        for n in JUDGE:
            log(f"{name:22s} {n}t " + line(res[n]) + f"  {notes[f'{n}t']}")
        log(f"{'':22s} {'PASS' if ok and not info else 'no: ' + '; '.join(why)[:400]}  [{time.time() - t0:.0f}s]")

    # A order type
    fam("A", "A1_limit_open_2m", "limit", {"x": 0, "to": 2})
    fam("A", "A2_limit_1t_better_2m", "limit", {"x": -1, "to": 2})
    fam("A", "A3_limit_2t_better_2m", "limit", {"x": -2, "to": 2})
    fam("A", "A4_limit_2m_then_market", "chase", {"x": 0, "to": 2})
    fam("A", "A5_limit_open_1m", "limit", {"x": 0, "to": 1})
    # B worst leg (picked on 2026 H1)
    lt = leg_table()
    drop = {m: lt[m]["1t"]["H1"]["per_month"] - lt[m]["10t"]["H1"]["per_month"] for m in lt}
    worst = max(drop, key=drop.get)
    out["B"]["legs"] = lt
    out["B"]["h1_drop_1_to_10"] = drop
    out["B"]["worst"] = worst
    log(f"B legs: H1 $ a month lost 1t->10t {drop}; worst {worst}")
    for m in lt:
        log(f"   {m}: " + " | ".join(f"{k} " + " ".join(f"{sp} PF {v[sp]['pf']} ${v[sp]['per_month']}" for sp in FXS) for k, v in lt[m].items()))
    fam("B", f"B1_drop_{worst}", "drop", {"src": worst})
    fam("B", f"B2_half_{worst}", "half", {"src": worst}, w={worst: 0.5})
    fam("B", f"B3_{worst}_plus60s", "late_leg", {"src": worst, "k": 1}, testable=False, info=True)
    # C entry minute
    p1 = c1_pick()
    out["C"]["c1_pick"] = p1
    log(f"C1 pick (2026 H1, 10t): {p1}")
    fam("C", "C1_leg_minute", "c1", {m: v["k"] for m, v in p1.items()}, testable=False, info=True)
    fam("C", "C2_next_5m_open", "c2")
    p3 = c3_pick()
    out["C"]["c3_pick"] = p3
    log(f"C3 pick (2026 H1, 10t): {p3}")
    fam("C", "C3_leg_0_or_5min", "c3", {m: v["late5"] for m, v in p3.items()})
    # E guards
    for name, g in GUARDS.items():
        res = {n: score(to_T(opt_units("base", n)[0]), n_paths, guard=g) for n in JUDGE}
        ok, why = gate_e(res, base)
        out["E"][name] = {"spec": g, "pass": ok, "why": why, **{f"{n}t": v for n, v in res.items()}}
        for n in JUDGE:
            log(f"{name:22s} {n}t " + line(res[n]))
        log(f"{'':22s} {'PASS' if ok else 'no: ' + '; '.join(why)[:400]}  [{time.time() - t0:.0f}s]")
    out["passers"] = [nm for f in ("A", "B", "C", "E") for nm, r in out[f].items() if isinstance(r, dict) and r.get("pass")]
    out["took_s"] = round(time.time() - t0)
    save(out)
    log(f"passers: {out['passers']}  took {out['took_s']}s")
    return out


def line(r):
    s = []
    for b in BASES:
        if b in r:
            s.append(b + " " + " ".join(f"{sp} ${r[b][sp]['usd_m']} 1st {r[b][sp]['first']} 2nd {r[b][sp]['second']} lost {r[b][sp]['lost_6m']}% "
                                        f"(pre-1st {r[b][sp]['lost_before_1st']})" for sp in SPANS))
    x = r["fixed"]
    s.append("fixed " + " ".join(f"{sp} {x[sp]['tpw']}/wk PF {x[sp]['pf']} ${x[sp]['per_month']}" for sp in FXS))
    return " | ".join(s)


def save(block, key=None):
    cur = {}
    if os.path.exists(OUT):
        try:
            cur = json.load(open(OUT, encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cur = {}
    if key:
        cur[key] = block
    else:
        cur.update(block)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(cur, fh, indent=1, default=float)


# ================================================================================================ D: ES legs
ES_PV = 5.0


def es_stats(rows, a, z, n_ticks, usd=250.0):
    import datetime as dt
    L = [t for t in rows if a <= t["day"] <= z]
    days = 0
    d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(z)
    days = sum(1 for i in range((d1 - d0).days + 1) if (d0 + dt.timedelta(i)).weekday() < 5)
    p = []
    for t in sorted(L, key=lambda t: t["entry_t"]):
        risk = float(t["risk_pts"])
        tgt = str(t.get("exit_kind", "")).upper().startswith("TARGET") or str(t.get("exit_kind", "")).lower() == "target"
        extra = (n_ticks - 1) * TICK * (1 if tgt else 2)
        pts = float(t["pts"]) - extra
        q = int(usd // ((risk + TICK) * ES_PV + COMM))
        if q > 0:
            p.append(q * (pts * ES_PV - COMM))
    p = np.array(p, float)
    eq = np.cumsum(p) if len(p) else np.zeros(1)
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    return {"n": len(p), "tpw": round(len(p) / max(1, days / 5), 2), "pf": round(float(gw / gl), 2) if gl > 0 else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / max(1, days / 21)),
            "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())) if len(p) else 0}


def cmd_es(log=print):
    p = os.path.join(ROOT, "research", "second", "atlas_es_trades.json")
    o = json.load(open(p, encoding="utf-8"))
    spans = {"2025": ("2025-04-14", "2025-12-31"), "H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-16")}
    out = {"method": o.get("method"), "scaled_params": o.get("scaled_params"), "nq_parity": o.get("nq_parity"), "legs": {}}
    for m in ("EMA", "MD", "SR"):
        rows = o["trades"].get(m) or []
        nq = {}
        for n in (6, 10):
            U = [AF().priced(u, n, n) for u in AF().units() if u["src"] == m]
            fx = fixed(to_T(U))
            nq[f"{n}t"] = {"H1": fx["H1"], "H2": fx["H2"], "2025": nq_span(U, "2025-04-14", "2025-12-31")}
        es = {}
        for lab, n_es in (("nq6_equiv", 2), ("nq10_equiv", 3), ("es10_stress", 10)):
            es[lab] = {sp: es_stats(rows, a, z, n_es) for sp, (a, z) in spans.items()}
        ok = all((es[e][sp]["pf"] or 0) > (nq[n][sp]["pf"] or 0) and es[e][sp]["per_month"] > nq[n][sp]["per_month"]
                 for e, n in (("nq6_equiv", "6t"), ("nq10_equiv", "10t")) for sp in spans)
        out["legs"][m] = {"nq": nq, "es": es, "beats_nq_all": ok}
        for e in es:
            log(f"ES {m} {e}: " + " | ".join(f"{sp} {v['n']} tr {v['tpw']}/wk PF {v['pf']} ${v['per_month']}/mo dd {v['max_dd']}" for sp, v in es[e].items()))
        for n in nq:
            log(f"NQ {m} {n}: " + " | ".join(f"{sp} {v['tpw']}/wk PF {v['pf']} ${v['per_month']}/mo" for sp, v in nq[n].items()))
        log(f"   ES {m} beats NQ everywhere: {ok}")
    save(out, "D")
    return out


def nq_span(U, a, z):
    S = [d for d in AM().sessions() if a <= d <= z]
    T = [t for t in to_T(U) if a <= t["day"] <= z]
    p = np.array([usd250(t) for t in T], float)
    eq = np.cumsum(p) if len(p) else np.zeros(1)
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    return {"n": len(p), "tpw": round(len(p) / max(1, len(S) / 5), 2), "pf": round(float(gw / gl), 2) if gl > 0 else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / max(1, len(S) / 21)),
            "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())) if len(p) else 0}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "es", "show"])
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        cmd_run(a.n)
    elif a.cmd == "es":
        cmd_es()
    else:
        o = json.load(open(OUT, encoding="utf-8"))
        print(json.dumps({"passers": o.get("passers")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
