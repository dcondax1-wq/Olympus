"""Zlarior's TWO live evals on ONE Monte Carlo (night-litplus 2026-11-18, research/writeups/lit-ideas-2026-11-18b.md).
PAPER RESEARCH ONLY: reads stored trades, writes research/lab/lit_two_evals.json, changes nothing live (no live_model*.json,
no engine file, no preset).

The owner runs Zlarior (LIT) on two MFFU evals at once, on the SAME signals:
  Z50  the Builder 50K eval from its real hole (2026-11-17: $49,192.78, floor $48,168.20 = $1,025 room, $3,807 to go,
       ~session 23), LIT live two_week (40% of the room to session 80, then safe_eval 60%; tools/money/builder_levers.Zlit50).
  N25  the Builder 25K #2 eval, fresh ($25,000), the bot's own mffu_builder_25k preset (40% of the room to session 80, then
       safe_eval 60%; tools/money/builder25k_eval.cfg_of({})).
Both step on the SAME 5-session-block paths (tools/uprisk.mc_paths), so a LIT losing streak hits both at once.

Pre-declared variants (one version each, fixed before any result; nothing tuned):
  today    as live.
  zombie   ATLAS's approved zombie-eval rule (engine/account_b.last_bullet 0.8 + eval give-up under $200 of room) ported
           to Zlarior: when the live eval sizing says 0 micros only because 1 micro does not fit the room share (40%; 60%
           after session 80), take 1 micro if its full stop-out (stop + 2 ticks + $1.90) fits 80% of the room, then the soft
           daily loss guard (engine/account_b.dll_guard); an eval under $200 of room is given up and a fresh one bought (the
           50K's research stuck line is already $200; the 25K's goes $100 -> $200). Uses ATLAS's own functions.
  stagger  one bad day does not hit both evals equally: LIT signals alternate - on the 1st, 3rd, 5th ... signal of the path
           the 50K takes its normal size and the 25K half of its normal size (engine idm_m 0.5: rounded down, at least 1
           micro, then every live cap); on the 2nd, 4th ... the other way round. Funded accounts unchanged.

Metrics per span (H1 = 2026 Jan-Jun pick, H2 = 2026 Jul-Oct check, REF = 2021-11..2025 reference; 1,000 paths each):
  evals    one eval each from today's state, 60 sessions, no re-buy: pass / fail (incl. given up) within 10 / 20 / 60
           sessions, median sessions to pass; joint: both dead, at least one passed, neither passed.
  seats    eval -> 2 sessions paperwork -> funded (LIT alone: UP50 / UP25, today's live funded rules) -> a fresh eval after a
           fail / give-up / lost funded account ($91.80 / $63), 126 sessions: $ a month to the owner after fees, first payout,
           no payout in 6 months; joint: first payout of either, no payout on both.
Costs $1.90 a micro + 1 tick (stored trades), MFFU rules as builder_levers (EOD trailing, lock, soft daily loss).

    python -X utf8 tools/money/lit_two_evals.py            # n=1000 -> research/lab/lit_two_evals.json
    python -X utf8 tools/money/lit_two_evals.py --n 200    # quicker
    python -X utf8 tools/money/lit_two_evals.py check      # base == builder25k_eval (fresh 25K) and builder_levers (50K)
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import builder_levers as BL  # noqa: E402
import builder25k_eval as B25  # noqa: E402

SA, U, A4 = BL.SA, BL.U, BL.A4
ROOT = BL.ROOT
from engine import account_b as EAB  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402

PV, COMM, SLIP = BL.PV, BL.COMM, BL.SLIP
OUT = os.path.join(ROOT, "research", "lab", "lit_two_evals.json")
SPANS = ("H1", "H2", "REF")
LEN, GAP, MO = U.LEN, U.GAP, U.LEN / 21.0
START = "2026-11-19"
P50, P25 = 91.80, 63.00
Z50_TODAY = {"room": 1024.58, "to_go": 3807.22, "session": 23}      # 2026-11-17 (STATE.md): $49,192.78, floor $48,168.20
E50, E25 = BL.E50, BL.E25
LB_SHARE, GIVE_UP = 0.8, 200.0                                       # ATLAS's zombie-eval rule (engine/account_b, 2026-11-15)
VARIANTS = {"today": {}, "zombie": {"lb": LB_SHARE, "give_up": GIVE_UP}, "stagger": {"stagger": 0.5}}
# --diag, EXPLANATION / REFERENCE ONLY (not candidates; never picked from): the zombie rule's two parts apart, and the
# builder-levers purchase lever re-measured from today's hole (a fresh 50K eval bought now next to the hole, both trade the
# same signal, the first 50K pass is kept: MFFU funds one Builder 50K; not a strategy change)
DIAG = {"zombie: last bullet only": {"lb": LB_SHARE}, "zombie: give-up $200 only": {"give_up": GIVE_UP},
        "ref: + a fresh 50K eval now ($91.80)": {"fresh50": True}}
WORDS = {"today": "today (both evals as live)",
         "zombie": "zombie-eval rule on both evals (last bullet 80% + give up under $200)",
         "stagger": "stagger: the two evals alternate full / half size on each signal"}


# ================================================================================================ one eval
class LEv(BL.GEv):
    """builder_levers.GEv (one MFFU Builder eval, a session at a time, any start state) with the live LIT eval sizing
    (engine/sizing.lit_qty) + the research options: a per-trade multiplier t["m"] (engine idm_m: before the live caps) and
    the zombie last bullet (engine/account_b.last_bullet + dll_guard). Counts the LIT signals it skipped for room."""

    def __init__(self, E, cfg, start=None, stuck=None, lb=None):
        super().__init__(E, {"LIT": ("lit", cfg)}, stuck=stuck, start=start)
        self.sub = {k: v for k, v in cfg.items() if not k.startswith("_")}
        self.lb = lb
        self.cnt = collections.Counter()

    def qty(self, t, st, room):
        m0 = qty_for(t["risk"])
        if not m0:
            return 0
        tr = {"risk_pts": t["risk"], "tgt_pts": t["tgt"] or 2.0 * t["risk"], "size_mult": 1.0}
        m = float(t.get("m", 1.0))
        if abs(m - 1.0) > 1e-9:
            tr.update(idm_m=m, idm_cap=None, wk_m=1.0)
        r = SZ.lit_qty(m0, tr, self.sub, room=room, state=st, learning=None, max_micros=self.E["maxq"])
        q = int(r["qty"])
        self.cnt["signals"] += 1
        if q <= 0:
            why = [str(x) for x in (r.get("reasons") or [])]
            room_skip = any("skip:" in x and "room" in x for x in why) and not any("already reached" in x for x in why)
            self.cnt["skip_room"] += room_skip
            if self.lb and room_skip:
                r2 = EAB.last_bullet(r, float(t["risk"]), float(self.lb), st)
                if int(r2.get("qty") or 0) > 0:
                    r2 = EAB.dll_guard(r2, float(t["risk"]), {"dll": self.E["dll"]}, st)
                    q = int(r2.get("qty") or 0)
                    self.cnt["last_bullet"] += q > 0
        return min(q, int(self.E["maxq"]))

    def step(self, ts):
        """= builder_levers.GEv.step with this sizer and the day's LIT count (n_today)."""
        E = self.E
        dll = E["dll"]
        self.s += 1
        wkey = (self.s - 1) // 5
        cum, traded, nlit = 0.0, False, 0
        for t in ts:
            if cum <= -dll:
                break
            room = self.bal + cum - self.floor
            st = {"profit": self.bal, "cum": cum, "room": room, "session": self.s, "n_today": nlit,
                  "wk_pnl": self.wk.get(wkey, 0.0), "days_traded": self.dtr}
            q = self.qty(t, st, room) if t.get("strat", "LIT") == "LIT" else 0
            if q <= 0:
                continue
            traded = True
            nlit += 1
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
        if self.bal <= self.floor:
            return "fail", round(cum, 2)
        self.peak = max(self.peak, self.bal)
        self.floor = min(max(self.floor, self.peak - E["mll"]), E["lock"])
        if self.bal >= E["tgt"]:
            return "pass", round(cum, 2)
        if self.bal - self.floor < self.stuck:
            return "stuck", round(cum, 2)
        return None, round(cum, 2)


def cfg50():
    return BL.ecfg50()


def cfg25():
    return B25.cfg_of({})


def mk_eval(acct, var, start=None):
    """A fresh (or from `start`) eval of account Z50 / N25 under variant var."""
    lb = var.get("lb")
    if acct == "Z50":
        stuck = max(E50["stuck"], float(var.get("give_up") or 0.0))
        return LEv(E50, cfg50(), start=start, stuck=stuck, lb=lb)
    stuck = max(float(B25.RULES["min_room"]), float(var.get("give_up") or 0.0))
    return LEv(E25, cfg25(), start=start, stuck=stuck, lb=lb)


def mults(seq, BY, f):
    """stagger: per session of the path, the (Z50, N25) multiplier lists for its LIT trades (global signal parity)."""
    out, j = [], 0
    for si in seq:
        a, b = [], []
        for _t in BY[si]:
            a.append(1.0 if j % 2 == 0 else f)
            b.append(f if j % 2 == 0 else 1.0)
            j += 1
        out.append((a, b))
    return out


def with_m(ts, ms):
    return [dict(t, m=m) if abs(m - 1.0) > 1e-9 else t for t, m in zip(ts, ms)]


class Either:
    """Two 50K evals on the same signal (the hole + a fresh one): passed when either passes, dead when both are."""

    def __init__(self, evs):
        self.evs = list(evs)
        self.cnt = collections.Counter()

    def step(self, ts):
        out = None
        for e in list(self.evs):
            r, _ = e.step(ts)
            if r == "pass":
                out = "pass"
            elif r:
                self.evs.remove(e)
        for e in self.evs:
            self.cnt.update(e.cnt)
            e.cnt.clear()
        if out:
            return out, 0.0
        return ("fail", 0.0) if not self.evs else (None, 0.0)


# ================================================================================================ the evals from today
def evals_from_today(BY, paths, var, h=60):
    """One eval each (Z50 from its hole, N25 fresh), the same path, no re-buy. -> per-account outcomes + joint."""
    rows = []
    cnt = {"Z50": collections.Counter(), "N25": collections.Counter()}
    for seq in paths:
        z = mk_eval("Z50", var, start=Z50_TODAY)
        ev = {"Z50": Either([z, mk_eval("Z50", var)]) if var.get("fresh50") else z, "N25": mk_eval("N25", var)}
        res = {k: ("open", h) for k in ev}
        live = set(ev)
        M = mults(seq[:h], BY, var["stagger"]) if var.get("stagger") else None
        for k, si in enumerate(seq[:h]):
            for nm in list(live):
                ts = BY[si]
                if M is not None:
                    ts = with_m(ts, M[k][0] if nm == "Z50" else M[k][1])
                r, _ = ev[nm].step(ts)
                if r:
                    res[nm] = ("pass" if r == "pass" else "fail", k + 1)
                    live.discard(nm)
            if not live:
                break
        for nm in ev:
            cnt[nm].update(ev[nm].cnt)
        rows.append(res)
    n = len(rows)

    def acc(nm):
        o = [r[nm] for r in rows]
        pas = [u for x, u in o if x == "pass"]
        return {"p10": round(100.0 * sum(1 for x, u in o if x == "pass" and u <= 10) / n, 1),
                "f10": round(100.0 * sum(1 for x, u in o if x == "fail" and u <= 10) / n, 1),
                "p20": round(100.0 * sum(1 for x, u in o if x == "pass" and u <= 20) / n, 1),
                "f20": round(100.0 * sum(1 for x, u in o if x == "fail" and u <= 20) / n, 1),
                "p60": round(100.0 * len(pas) / n, 1), "f60": round(100.0 * sum(1 for x, _ in o if x == "fail") / n, 1),
                "open60": round(100.0 * sum(1 for x, _ in o if x == "open") / n, 1),
                "pass_med": float(np.median(pas)) if pas else None,
                "signals": cnt[nm]["signals"], "skip_room_pct": round(100.0 * cnt[nm]["skip_room"] / max(1, cnt[nm]["signals"]), 1),
                "last_bullets": cnt[nm]["last_bullet"]}

    def joint(fn):
        return round(100.0 * sum(1 for r in rows if fn(r)) / n, 1)

    dead = lambda r, nm, h_: r[nm][0] == "fail" and r[nm][1] <= h_            # noqa: E731
    pas_ = lambda r, nm, h_: r[nm][0] == "pass" and r[nm][1] <= h_            # noqa: E731
    return {"Z50": acc("Z50"), "N25": acc("N25"),
            "joint": {"both_dead20": joint(lambda r: dead(r, "Z50", 20) and dead(r, "N25", 20)),
                      "both_dead60": joint(lambda r: dead(r, "Z50", 60) and dead(r, "N25", 60)),
                      "one_pass10": joint(lambda r: pas_(r, "Z50", 10) or pas_(r, "N25", 10)),
                      "one_pass20": joint(lambda r: pas_(r, "Z50", 20) or pas_(r, "N25", 20)),
                      "both_pass60": joint(lambda r: pas_(r, "Z50", 60) and pas_(r, "N25", 60)),
                      "none_pass60": joint(lambda r: not pas_(r, "Z50", 60) and not pas_(r, "N25", 60))}}


# ================================================================================================ the seats (6 months)
def seats(BY, paths, var, cal):
    """Both accounts' seats (eval -> funded -> re-buy) on the same paths. -> per-account seat stats + joint."""
    out = {"Z50": [], "N25": []}
    for seq in paths:
        zs = BL.Seat(lambda _=None: mk_eval("Z50", var), lambda: BL.GF("builder50k", U.UP50, BL.F50_LIT), P50,
                     [mk_eval("Z50", var, start=Z50_TODAY)] + ([mk_eval("Z50", var)] if var.get("fresh50") else []),
                     cost0=P50 if var.get("fresh50") else 0.0)
        ns = BL.Seat(lambda _=None: mk_eval("N25", var), lambda: BL.GF("builder25k", U.UP25, {"LIT": ("fq", None)}), P25,
                     [mk_eval("N25", var)])
        M = mults(seq[:LEN], BY, var["stagger"]) if var.get("stagger") else None
        for k, si in enumerate(seq[:LEN]):
            ts = BY[si]
            zs.step(k, with_m(ts, M[k][0]) if M is not None else ts, ts)
            ns.step(k, with_m(ts, M[k][1]) if M is not None else ts, ts)
        out["Z50"].append(zs)
        out["N25"].append(ns)
    res = {nm: BL.seat_stats(v, cal) for nm, v in out.items()}
    n = len(paths)
    fz = [s.first_pay for s in out["Z50"]]
    fn = [s.first_pay for s in out["N25"]]
    first = [min([x for x in (a, b) if x] or [None]) if (a or b) else None for a, b in zip(fz, fn)]
    got = [x for x in first if x]
    tot = np.array([(a.owner - a.cost) + (b.owner - b.cost) for a, b in zip(out["Z50"], out["N25"])])
    res["joint"] = {"first_pay_either_med": float(np.median(got)) if got else None,
                    "first_pay_either_date": cal[int(round(float(np.median(got)))) - 1] if got else None,
                    "no_pay_both_6m": round(100.0 * sum(1 for x in first if not x) / n, 1),
                    "net_m": round(float(tot.mean()) / MO), "net_m_p10": round(float(np.percentile(tot, 10)) / MO),
                    "fees_6m": round(float(np.mean([a.cost + b.cost for a, b in zip(out["Z50"], out["N25"])])), 1)}
    return res


# ================================================================================================ main
def check(n=300):
    """Base parity: the fresh 25K == builder25k_eval's live pick; the 50K hole == builder_levers GEv (same paths)."""
    S = SA.data()["S"]
    BY = BL.by_mix(("LIT",))
    ok = True
    for sp in ("H1", "H2"):
        PE = U.mc_paths(S, sp, n, length=60, seed=A4.SEED_EVAL)
        a = B25.eval_one(BY, PE, B25.BASE)
        b = []
        for seq in PE:
            e = mk_eval("N25", {})
            out, used = "open", 60
            for k, si in enumerate(seq[:60]):
                r, _ = e.step(BY[si])
                if r:
                    out, used = ("pass" if r == "pass" else "fail"), k + 1
                    break
            b.append((out, used))
        pas = [u for o, u in b if o == "pass"]
        mine = {"p10": round(100.0 * sum(1 for o, u in b if o == "pass" and u <= 10) / n, 1),
                "f60": round(100.0 * sum(1 for o, _ in b if o == "fail") / n, 1), "pass_med": float(np.median(pas)) if pas else None}
        same = abs(mine["p10"] - a["p10"]) < 1e-9 and abs(mine["f60"] - a["f60"]) < 1e-9 and mine["pass_med"] == a["pass_med"]
        print(f"check 25K {sp}: builder25k_eval {a['p10']}/{a['f60']} med {a['pass_med']} | here {mine} -> {'OK' if same else 'DIFF'}")
        ok &= same
        q = BL.eval_quick(BY, PE, lambda: BL.GEv(E50, BL.Zlit50(), start=Z50_TODAY))
        b = []
        for seq in PE:
            e = mk_eval("Z50", {}, start=Z50_TODAY)
            out, used = "open", 60
            for k, si in enumerate(seq[:60]):
                r, _ = e.step(BY[si])
                if r:
                    out, used = ("pass" if r == "pass" else "fail"), k + 1
                    break
            b.append((out, used))
        p10 = round(100.0 * sum(1 for o, u in b if o == "pass" and u <= 10) / n, 1)
        f60 = round(100.0 * sum(1 for o, _ in b if o == "fail") / n, 1)
        same = abs(p10 - q["p10"]) < 1e-9 and abs(f60 - q["f60"]) < 1e-9
        print(f"check 50K hole {sp}: builder_levers {q['p10']}/{q['f60']} | here {p10}/{f60} -> {'OK' if same else 'DIFF'}")
        ok &= same
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=("run", "check"))
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--diag", action="store_true", help="also the zombie rule's two parts apart (explanation only)")
    a = ap.parse_args(argv)
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    if a.cmd == "check":
        return check()
    import payout_plan as PP
    t0 = time.time()
    cal = PP.calendar(LEN + 5, START)
    S = SA.data()["S"]
    BY = BL.by_mix(("LIT",))
    res = {"date": "2026-11-18", "n": a.n, "start": START, "z50_today": Z50_TODAY, "prices": {"builder50k": P50, "builder25k": P25},
           "variants": {k: {"words": WORDS[k], **v} for k, v in VARIANTS.items()}, "spans": U.SPAN, "rows": {}}
    for sp in SPANS:
        PE = U.mc_paths(S, sp, a.n, length=60, seed=A4.SEED_EVAL)
        PF = U.mc_paths(S, sp, a.n, length=LEN, seed=A4.SEED_LIFE)
        res["rows"][sp] = {}
        for nm, var in list(VARIANTS.items()) + (list(DIAG.items()) if a.diag else []):
            t1 = time.time()
            ev = evals_from_today(BY, PE, var)
            st = seats(BY, PF, var, cal)
            res["rows"][sp][nm] = {"evals": ev, "seats": st}
            z, n_, j = ev["Z50"], ev["N25"], ev["joint"]
            print(f"{sp:3s} {nm[:26]:26s} 50K 2w {z['p10']}/{z['f10']} 60s {z['p60']}/{z['f60']} med {z['pass_med']} skip {z['skip_room_pct']}% lb {z['last_bullets']} | "
                  f"25K 2w {n_['p10']}/{n_['f10']} 60s {n_['p60']}/{n_['f60']} med {n_['pass_med']} skip {n_['skip_room_pct']}% lb {n_['last_bullets']} | "
                  f"both dead 20/60 {j['both_dead20']}/{j['both_dead60']} one pass 10/20 {j['one_pass10']}/{j['one_pass20']} | "
                  f"seat $/mo 50K {st['Z50']['net_m']} 25K {st['N25']['net_m']} both {st['joint']['net_m']} (p10 {st['joint']['net_m_p10']}) "
                  f"1st pay 50K {st['Z50']['first_pay_med']} 25K {st['N25']['first_pay_med']} either {st['joint']['first_pay_either_med']} "
                  f"nopay both {st['joint']['no_pay_both_6m']}% ({time.time() - t1:.0f}s)", flush=True)
    if not a.no_save:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1, default=float)
        print("wrote", os.path.relpath(OUT, ROOT))
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
