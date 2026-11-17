"""An "edge stopped working" switch that needs no prediction (owner idea 2026-11-17). Write-up:
research/writeups/drift-switch-2026-11-17.md. PAPER RESEARCH ONLY: reads stored trades, writes research/lab/drift_switch.json,
changes nothing live (no live_model*.json, no engine file).

Idea: LIT (and ATLAS) earn in 2026 but about $0 in 2021-25. Instead of predicting the regime, watch each strategy's OWN record
of finished trades and cut its size (x0.5 / x0.25 / paper = skip, still recorded) while the record drifts below expectation;
restore as soon as the record recovers (the rule clears on the shadow record, paper trades included).

Rules (on the strategy's own net R = pts / stop pts, every trade closed before this entry, 2021-11 on, paper trades included):
  sum N, thr   the last N trades sum <= thr R                     N 20 / 30 / 50, thr 0 / -5
  pf N, p      the last N trades' profit factor < p                N 30 / 50, p 1.0 / 1.2
  run K        the last K trades all losers (R < 0)                K 4 / 6 / 8   (restored by the next winner)
  dd X, D      cumulative R is D R or more under its best of the last X trades     X 50: D 5 / 10 / 15, X 100: D 10
  x every rule: cut to x0.5, x0.25, or paper (x0)  -> 17 rules x 3 levels = 51 variants (+ "off" = today).
Sizing: the account's normal size first (live two_week eval, UP50 funded, stack_q for ATLAS), then x the multiplier, rounded
down, never below 1 micro while > 0; paper skips the trade (its R still enters the record).

Scored on exactly the trades / account sims / Monte Carlo paths of tools/money/stack_one_account.py (costs in: $1.90 a micro,
1 tick on market fills and stops; the Rapid EOD funded Tier-1 news rule):
  plain      the real days in order at a fixed $500 a trade (LIT; ATLAS $500 on the Rapid mix): trades/wk, PF, net $, $/mo, max DD
  builder    MFFU Builder 50K, LIT alone (today's plan): eval 2,000 x 60 sessions, funded + 6-month slot 1,000 x 126
  rapid      MFFU Rapid EOD 50K, LIT + ATLAS $500 (the owner's next account): same
Gate (pre-registered): in BOTH 2026 halves the 6-month slot $ a month after fees on both accounts >= 95% of today (Jan-Jun
picks, Jul-Oct checks); and in 2021-25 the plain net $ higher, the plain max DD smaller, and on both accounts the slot $ higher
with no more failed evals per slot and no more fees. Chance: every variant again with its 2021-25 cut pattern circularly shifted to
a random place inside 2021-25 (same share of trades cut, same streak lengths, 2026 left as the rule has it): how many shifted
variants pass the same gate. That asks the real question: does the switch cut at the RIGHT times, or would any cuts of the same
size do as well.

    python -X utf8 tools/money/drift_switch.py             # -> research/lab/drift_switch.json (~25 min)
    python -X utf8 tools/money/drift_switch.py --n 300     # quicker
"""
from __future__ import annotations

import argparse
import heapq
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stack_one_account as S1  # noqa: E402

A4, U, SZ, FM, qty_for = S1.A4, S1.U, S1.SZ, S1.FM, S1.qty_for
PV, COMM, SLIP = S1.PV, S1.COMM, S1.SLIP
ROOT = S1.ROOT
OUT = os.path.join(ROOT, "research", "lab", "drift_switch.json")
SPANS = S1.SPANS


# ================================================================================================ the rules
def r_of(t):
    return float(t["pts"]) / max(1e-9, float(t["risk"]))


def rule_sum(n, thr):
    return lambda h: len(h) >= n and sum(h[-n:]) <= thr


def rule_pf(n, p):
    def f(h):
        if len(h) < n:
            return False
        w = h[-n:]
        g = sum(x for x in w if x > 0)
        l = -sum(x for x in w if x < 0)
        return (g / l if l > 0 else 99.0) < p
    return f


def rule_run(k):
    return lambda h: len(h) >= k and all(x < 0 for x in h[-k:])


def rule_dd(x, d):
    def f(h):
        if len(h) < 5:
            return False
        c = np.cumsum([0.0] + list(h[-x:]))
        return c[-1] <= c.max() - d
    return f


RULES = {}
for _n in (20, 30, 50):
    for _t in (0.0, -5.0):
        RULES[f"sum{_n}<={_t:g}R"] = rule_sum(_n, _t)
for _n in (30, 50):
    for _p in (1.0, 1.2):
        RULES[f"pf{_n}<{_p:g}"] = rule_pf(_n, _p)
for _k in (4, 6, 8):
    RULES[f"{_k} losers in a row"] = rule_run(_k)
for _x, _d in ((50, 5), (50, 10), (50, 15), (100, 10)):
    RULES[f"dd{_d}R under the {_x}-trade high"] = rule_dd(_x, _d)
LEVELS = {"x0.5": 0.5, "x0.25": 0.25, "paper": 0.0}
VARIANTS = {"off": None, **{f"{r} -> {lv}": (r, m) for r in RULES for lv, m in LEVELS.items()}}


def records():
    """Each strategy's trades in entry order (LIT 2021-11 .. 2026-10 incl. the 120 live 2026 trades; ATLAS likewise)."""
    D = S1.data()
    rec = {"LIT": [t for ts in D["LIT"] for t in ts]}
    rec["ATLAS"] = sorted((t for d in sorted(D["OTHER"]) for t in D["OTHER"][d] if t["strat"] == "ATLAS"), key=lambda t: t["entry_t"])
    return rec


def cold_mask(trades, rule):
    """True for a trade entered while the rule is on (history = trades closed before its entry)."""
    hist, out, pend = [], [], []
    for t in trades:
        while pend and pend[0][0] <= t["entry_t"]:
            _, _, r = heapq.heappop(pend)
            hist.append(r)
        out.append(bool(rule(hist)))
        heapq.heappush(pend, (t["exit_t"], len(out), r_of(t)))
    return np.array(out, dtype=bool)


_MASK = {}


def masks(rule_name):
    if rule_name not in _MASK:
        _MASK[rule_name] = {s: cold_mask(ts, RULES[rule_name]) for s, ts in records().items()}
    return _MASK[rule_name]


def dm_map(variant, shift=None):
    """(strat, entry_t) -> multiplier. shift = {strat: k}: the cut pattern rolled k trades (the chance control)."""
    v = VARIANTS[variant]
    if v is None:
        return {}
    rn, m = v
    out = {}
    for s, ts in records().items():
        mk = masks(rn)[s]
        if shift:                                  # roll the cut pattern inside 2021-25 only (2026 kept as the rule has it)
            nr = sum(1 for t in ts if t["day"] < "2026-01-01")
            mk = np.r_[np.roll(mk[:nr], shift[s] % nr), mk[nr:]]
        for t, c in zip(ts, mk):
            if c:
                out[(s, t["entry_t"])] = m
    return out


def apply_dm(BY, dm):
    """Per-session trades with "dm" attached; a paper trade (x0) leaves the account."""
    if not dm:
        return BY
    out = []
    for ts in BY:
        row = []
        for t in ts:
            m = dm.get((t["strat"], t["entry_t"]), 1.0)
            if m <= 0:
                continue
            row.append({**t, "dm": m} if m != 1.0 else t)
        out.append(row)
    return out


def scale(q, t):
    m = t.get("dm", 1.0)
    if q <= 0 or m >= 1.0:
        return q
    return max(1, int(math.floor(q * m + 1e-9)))


# ================================================================================================ the account sims (stack_one_account + the multiplier)
class Ev(S1.Ev):
    def step(self, ts, keep=None):
        c, E = self.cfg, self.E
        dll = c.get("_dll", E["dll"])
        self.s += 1
        wkey = (self.s - 1) // 5
        cum, traded = 0.0, False
        sub = {k: v for k, v in c.items() if not k.startswith("_")}
        for t in ts:
            if cum <= -dll:
                break
            room = self.bal + cum - self.floor
            if t["strat"] == "LIT":
                m0 = qty_for(t["risk"])
                if not m0:
                    continue
                st = {"profit": self.bal, "cum": cum, "room": room, "session": self.s, "n_today": 0,
                      "wk_pnl": self.wk.get(wkey, 0.0), "days_traded": self.dtr}
                q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, sub, room=room, state=st,
                               learning=None, max_micros=c["_maxq"])["qty"]
                q = min(q, c["_maxq"])
            else:
                q = S1.stack_q(t, self.z, room, cum, c["_maxq"], min(dll, S1.SOFT_DLL))
            q = scale(q, t)
            q = S1.cons_cap(q, t, E.get("cons"), E["tgt"], cum)
            if q <= 0:
                continue
            traded = True
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            self.max_risk = max(self.max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            if self.bal + cum + low <= self.floor:
                return "fail", round(self.floor - self.bal, 2)
            cum += pnl
        self.bal += cum
        self.wk[wkey] = self.wk.get(wkey, 0.0) + cum
        if traded:
            self.dtr += 1
            self.best = max(self.best, cum)
        if self.bal <= self.floor:
            return "fail", round(cum, 2)
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - E["mll"]), E["lock"])
        if self.bal >= E["tgt"] and self.dtr >= E.get("min_days", 1) and (not E.get("cons") or self.best <= E["cons"] * self.bal + 1e-9):
            return "pass", round(cum, 2)
        if self.bal - self.floor < c["_stuck"]:
            return "stuck", round(cum, 2)
        return None, round(cum, 2)


class BuilderFunded(S1.BuilderFunded):
    def qty(self, t, st):
        return scale(super().qty(t, st), t)


class Rapid(S1.Rapid):
    def step(self, ts, keep=None):
        if self.state != "on":
            return None, None, 0.0
        R, c = self.R, self.cfg
        self.k += 1
        dll, mq, cap = self.dll(), self.maxq(), self.cap()
        A = {"mll": R["mll"], "lock": R["lock"], "dll": dll, "buffer": R["buffer"], "pay_min": R["pay_min"], "pay_max": cap,
             "split": R["split"], "cons": R["cons"] or 0.5, "cycle_days": 0, "first_wait": 0, "max_payouts": R["max_payouts"],
             "max_micros": mq, "scale": 1.0}
        cyc = {"cycle_start_bal": round(self.cyc_start, 2), "cycle_prev": round(sum(self.cyc), 2),
               "best_prev": round(max(self.cyc), 2) if self.cyc else 0.0, "cycle_days_prev": len(self.cyc), "payouts_n": len(self.pays),
               "cycle_target": round(max(0.0, R["buffer"] + min(cap, 2000.0) - self.cyc_start), 2)}
        cum = 0.0
        for t in ts:
            if cum <= -dll:
                break
            room = round(self.bal + cum - self.floor, 2)
            if t["strat"] == "LIT":
                st = {"room": room, "cum": cum, "locked": self.floor >= R["lock"] - 1e-9, "bal": self.bal, **cyc}
                q = min(SZ.funded_qty(t, st, c, acct=A), mq)
            else:
                q = S1.stack_q(t, self.z, room, cum, mq, min(dll, S1.SOFT_DLL))
            q = scale(q, t)
            if q <= 0:
                continue
            self.n_tr += 1
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            self.max_risk = max(self.max_risk, (t["risk"] + SLIP) * PV * q + COMM * q)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            if self.bal + cum + low <= self.floor:
                self.state = "lost"
                return "lost", None, round(self.floor - self.bal, 2)
            cum += pnl
        if abs(cum) > 1e-9:
            self.bal += round(cum, 2)
            self.cyc.append(round(cum, 2))
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - R["mll"]), R["lock"])
        above = self.bal - R["buffer"]
        if above >= R["pay_min"] and self.bal - self.cyc_start > 0:
            amt = round(min(cap, above), 2)
            self.pays.append(amt)
            self.bal -= amt
            self.cyc, self.cyc_start = [], self.bal
            if len(self.pays) >= R["max_payouts"]:
                self.state = "grad"
                return "grad", amt * self.split, round(cum, 2)
            return "paid", amt * self.split, round(cum, 2)
        return None, None, round(cum, 2)


# stack_one_account's eval_stats / Slot / plan() build these by their module names: point them at the multiplier versions
S1.Ev, S1.BuilderFunded, S1.Rapid = Ev, BuilderFunded, Rapid

ACCOUNTS = {"builder": ("builder", "LIT alone"), "rapid": ("rapid_eod", "LIT + ATLAS $500")}


def plain(BY, span):
    """Real days in order, $500 a trade (x the multiplier), costs in."""
    S = S1.data()["S"]
    a, z = U.span_ix(S, span)
    pnl, days, cut = [], [], 0
    for si in range(a, z):
        d = 0.0
        for t in BY[si]:
            q = scale(max(1, int(500.0 // ((t["risk"] + SLIP) * PV + COMM))), t)
            cut += t.get("dm", 1.0) < 1.0
            p = t["pts"] * PV * q - COMM * q
            pnl.append(p)
            d += p
        days.append(d)
    p = np.array(pnl) if pnl else np.zeros(1)
    eq = np.cumsum(days)
    gl = -p[p < 0].sum()
    ns = z - a
    return {"trades": len(pnl), "tpw": round(len(pnl) / (ns / 5.0), 2), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (ns / 21.0)),
            "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())), "cut": cut}


_BASE_BY = {}


def base_by(acc):
    if acc not in _BASE_BY:
        kind, mix = ACCOUNTS[acc]
        se, sf, z = S1.MIXES[mix]
        spec = S1.plan(kind, z)
        _BASE_BY[acc] = (spec, S1.mix_by(se), S1.mix_by(sf, news=bool(spec.get("news"))), S1.mix_by(sf))
    return _BASE_BY[acc]


def score(variant, acc, PE, PF, spans=SPANS, shift=None, full=True):
    spec, BYe0, BYf0, BYp0 = base_by(acc)
    dm = dm_map(variant, shift)
    BYe, BYf, BYp = apply_dm(BYe0, dm), apply_dm(BYf0, dm), apply_dm(BYp0, dm)
    o = {}
    for sp in spans:
        r = {"plain": plain(BYp, sp)}
        sl = A4.slot_stats(S1.run_slots(BYe, BYf, PF[sp], spec))
        r["slot"] = {k: sl[k] for k in ("net_m", "owner_m", "fees_6m", "p_neg", "p_no_pay", "evals", "first_pay_med", "pays")}
        if full:
            r["eval"] = S1.eval_stats(BYe, PE[sp], spec)
            r["funded"] = S1.funded_stats(BYf, PF[sp], spec)
        o[sp] = r
    return o


def gate(v, base):
    """The pre-registered test (module doc). v / base = {acc: {span: result}}."""
    chk = {}
    for acc in ACCOUNTS:
        for sp in ("H1", "H2"):
            b = base[acc][sp]["slot"]["net_m"]
            chk[f"{acc} {sp} slot $ >= 95%"] = v[acc][sp]["slot"]["net_m"] >= 0.95 * b
        a, b = v[acc]["REF"], base[acc]["REF"]
        chk[f"{acc} REF slot $ up"] = a["slot"]["net_m"] > b["slot"]["net_m"]
        # failed evals per slot = evals bought - 1 (each eval after the first follows a fail / a lost account)
        chk[f"{acc} REF fees not up"] = a["slot"]["fees_6m"] <= b["slot"]["fees_6m"] + 1e-9
    a, b = v["builder"]["REF"]["plain"], base["builder"]["REF"]["plain"]
    chk["REF plain net up"] = a["net"] > b["net"]
    chk["REF plain max DD smaller"] = a["max_dd"] > b["max_dd"]
    return all(chk.values()), chk


def pick_ok(v, base):
    """The Jan-Jun pick: both accounts' H1 slot $ >= 95% of today."""
    return all(v[acc]["H1"]["slot"]["net_m"] >= 0.95 * base[acc]["H1"]["slot"]["net_m"] for acc in ACCOUNTS)


def cut_share():
    """Share of each strategy's trades cut, per span (the real rule)."""
    rec = records()
    def span_of(d):
        return next((sp for sp in SPANS if U.SPAN[sp][0] <= d <= U.SPAN[sp][1]), None)
    out = {}
    for rn in RULES:
        mk = masks(rn)
        row = {}
        for s, ts in rec.items():
            for sp in SPANS:
                ix = [i for i, t in enumerate(ts) if span_of(t["day"]) == sp]
                row[f"{s} {sp}"] = round(100.0 * float(mk[s][ix].mean()), 1) if ix else None
        out[rn] = row
    return out


def plain_chance(n_draw=200, seed=5):
    """The trades alone (LIT, $500 a trade, real 2021-25 days in order): does the switch cut at the right times? For each
    variant, the share of random 2021-25 shifts of its own cut pattern that beat it on net $ and on max DD."""
    _, _, _, BYp0 = base_by("builder")
    rec = records()
    rng = np.random.default_rng(seed)
    out = {}
    for v in VARIANTS:
        if v == "off":
            continue
        real = plain(apply_dm(BYp0, dm_map(v)), "REF")
        nets, dds = [], []
        for _ in range(n_draw):
            sh = {s: int(rng.integers(1, 10 ** 6)) for s in rec}
            r = plain(apply_dm(BYp0, dm_map(v, sh)), "REF")
            nets.append(r["net"])
            dds.append(r["max_dd"])
        out[v] = {"net": real["net"], "max_dd": real["max_dd"], "shift_net_med": round(float(np.median(nets))),
                  "shift_dd_med": round(float(np.median(dds))),
                  "p_net": round(float(np.mean(np.array(nets) >= real["net"])), 3),
                  "p_dd": round(float(np.mean(np.array(dds) >= real["max_dd"])), 3)}
    return out


def study(n=1000, n_shift=10, log=print):
    S = S1.data()["S"]
    PE = {sp: U.mc_paths(S, sp, 2 * n, length=S1.H_EVAL, seed=A4.SEED_EVAL) for sp in SPANS}
    PF = {sp: U.mc_paths(S, sp, n, length=U.LEN, seed=A4.SEED_LIFE) for sp in SPANS}
    res = {}
    t0 = time.time()
    for v in VARIANTS:
        res[v] = {acc: score(v, acc, PE, PF) for acc in ACCOUNTS}
        b, r = res[v]["builder"], res[v]["rapid"]
        log(f"{v:44s} B slot {b['H1']['slot']['net_m']:>6}/{b['H2']['slot']['net_m']:>6}/{b['REF']['slot']['net_m']:>5} "
            f"fees {b['REF']['slot']['fees_6m']:>6} | R slot {r['H1']['slot']['net_m']:>6}/{r['H2']['slot']['net_m']:>6}/"
            f"{r['REF']['slot']['net_m']:>5} fees {r['REF']['slot']['fees_6m']:>6} | plain REF {b['REF']['plain']['net']:>7} "
            f"dd {b['REF']['plain']['max_dd']:>7}  ({time.time() - t0:.0f}s)")
    base = res["off"]
    verdict = {}
    for v in VARIANTS:
        if v == "off":
            continue
        ok, chk = gate(res[v], base)
        verdict[v] = {"passes": ok, "h1_pick_ok": pick_ok(res[v], base), "checks": chk}
    n_pass = sum(x["passes"] for x in verdict.values())
    log(f"real variants passing the gate: {n_pass} / {len(verdict)}")
    # chance: each variant with its cut pattern rolled to a random place in the record (slot $ only, smaller n)
    rng = np.random.default_rng(11)
    ns = max(200, n // 3)
    PEs = {sp: [p for p in PE[sp][: 2 * ns]] for sp in SPANS}
    PFs = {sp: [p for p in PF[sp][:ns]] for sp in SPANS}
    base_s = {acc: score("off", acc, PEs, PFs, full=False) for acc in ACCOUNTS}
    rec = records()
    shifted = []
    for v in verdict:
        for _ in range(n_shift):
            sh = {s: int(rng.integers(len(ts) // 10, len(ts) - len(ts) // 10)) for s, ts in rec.items()}   # taken mod the 2021-25 count
            r = {acc: score(v, acc, PEs, PFs, shift=sh, full=False) for acc in ACCOUNTS}
            ok, _ = gate(r, base_s)
            shifted.append({"variant": v, "passes": ok, "h1_pick_ok": pick_ok(r, base_s),
                            "builder": {sp: r["builder"][sp]["slot"]["net_m"] for sp in SPANS},
                            "rapid": {sp: r["rapid"][sp]["slot"]["net_m"] for sp in SPANS},
                            "ref_plain_net": r["builder"]["REF"]["plain"]["net"]})
        log(f"  shifted {v:44s} pass {sum(x['passes'] for x in shifted if x['variant'] == v)}/{n_shift}  ({time.time() - t0:.0f}s)")
    # the real variants once more on the same smaller paths, so the shifted ones compare like for like
    real_s = {}
    for v in verdict:
        r = {acc: score(v, acc, PEs, PFs, full=False) for acc in ACCOUNTS}
        real_s[v] = gate(r, base_s)[0]
    chance = {"n_shifted": len(shifted), "shifted_pass_pct": round(100.0 * sum(x["passes"] for x in shifted) / len(shifted), 1),
              "real_pass_pct_same_paths": round(100.0 * sum(real_s.values()) / len(real_s), 1),
              "real_pass_same_paths": [v for v, ok in real_s.items() if ok]}
    log(f"chance: real {chance['real_pass_pct_same_paths']}% vs shifted {chance['shifted_pass_pct']}%")
    chance["plain_ref"] = plain_chance(n_draw=200)
    return {"date": "2026-11-17", "n": n, "spans": U.SPAN, "accounts": {k: list(v) for k, v in ACCOUNTS.items()},
            "variants": res, "verdict": verdict, "n_pass": n_pass, "cut_share": cut_share(), "chance": chance,
            "shifted": shifted}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--shift", type=int, default=10, help="chance draws per variant")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    out = study(a.n, a.shift)
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
        print("wrote", os.path.relpath(OUT, ROOT))
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
