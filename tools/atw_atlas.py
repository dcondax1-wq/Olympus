"""ATLAS (account B, Builder 25K: EMA London pullback + MACD sweep + S/R NY reclaim) - round 2 of 2026-10-30:
research/writeups/atlas-windows-entries-2026-10-30.md. Research only: nothing here touches engine/, second_model.json,
live_model*.json or data/.

1. Per-member trading windows (PRE-REGISTERED before any score):
   For each member (EMA, MD, SR), on the 2026 H1 account-B candidates (after the no-hedge / LIT rules), group the trades by
   one calendar fact and pick the ONE bucket with the lowest total R (costs in; at least 3 trades and a negative total) -
   that bucket is skipped for that member from then on (at most one cut per member). Families:
     m30   30-minute bucket of the ET entry time
     m60   the entry hour (atlas-v2.md picked hours on 2021-24; this picks on 2026 H1)
     dow   weekday (atlas.md tried 14 weekday rules by hand: EMA no Thursday; done again here only as the frozen pick)
   Frozen, checked on 2026 H2, 2025 and 2021-24 (and per year: the skipped trades' R each year), with
     neighbours  the bucket before / after instead of the picked one (same member)
     controls    30 random-window draws: a random H1 bucket with trades for each member, same family, same scoring
2. Entry execution: instead of the market entry at the next 5m open, a LIMIT at a better price, working for N minutes:
     mid   the signal 5m bar's midpoint (when better than the market entry; else the market entry stays)
     q25   0.25 x the stop distance back toward the stop
     q50   0.50 x the stop distance back toward the stop
   timeout 15 / 30 minutes; not filled -> skip, or -> market at the next bar's open + 1 tick ("mkt"). A limit fills only
   when traded through by 1 tick (or gapped through at the open: filled at the open). Cancelled if the target is touched
   before the fill. The stop stays at the protected level (the sweep extreme), the target price stays; the smaller
   distance means more micros at the same $ risk (size follows the stop). On the fill bar only the stop counts (no target
   on the fill bar); the walk goes on from the next bar with the member's own management (engine/advisor.walk: EMA BE at
   +1R, MACD / S/R 15-minute check, flat 15:55). Bars: true 1m in 2026 (days with full 1m coverage), 5m otherwise. Money
   by the difference method of tools/structure_atlas.py: stored points + (variant walk - base walk).

Judged as before: tools/atlas_v2.score (account-B need size on the 25K, back-to-back eval paths, the v2 test: 2-week pass
up, dead not up, eval-path $ up in both 2026 halves, 2025 / 2021-24 not worse, 2+ candidate trades a week) and the $500 view
(each candidate risks $500, $1.90 a micro + 1 tick).

    python -X utf8 tools/atw_atlas.py windows    # -> research/second/atw_windows.json
    python -X utf8 tools/atw_atlas.py singles    # every single-bucket cut (30-min): how many pass by chance
    python -X utf8 tools/atw_atlas.py entries    # -> research/second/atw_entries.json
    python -X utf8 tools/atw_atlas.py save       # runs atw_* in the run library
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")
from tools import ab_edge as E  # noqa: E402
from tools import dsx_discretion as D  # noqa: E402

OUT_W = os.path.join(ROOT, "research", "second", "atw_windows.json")
OUT_E = os.path.join(ROOT, "research", "second", "atw_entries.json")
MEMBERS = ("EMA", "MD", "SR")
SP4 = ("H1", "H2", "2025", "2021-24")
MON = E.MONTHS_A
TICK = 0.25
FAMS = ("m30", "m60", "dow")
N_PL = 30


def bucket(u, fam):
    from tools import atlas as A
    if fam == "m30":
        return int(A.et_mod(u["entry_t"]) // 30)
    if fam == "m60":
        return int(A.et_mod(u["entry_t"]) // 60)
    return dt.date.fromisoformat(u["day"]).weekday()


def blabel(b, fam):
    if fam == "dow":
        return ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")[b]
    w = 30 if fam == "m30" else 60
    return f"{b * w // 60:02d}:{b * w % 60:02d}-{(b + 1) * w // 60:02d}:{(b + 1) * w % 60:02d}"


def view(U, sp_of, m=None):
    m = np.ones(len(U)) if m is None else m
    return {s: D.a_view([u for u, x in zip(U, sp_of) if x == s], m[sp_of == s], s) for s in SP4}


def compact(o, vw):
    keep = ("p10", "f10", "dead10", "dec10", "p15", "f15", "pass_med", "slow_pass", "mp_net_less_fees", "mp_passes", "tpw", "sig_tpw", "sig_wk2", "pf", "n")
    return {s: {**{k: o[s].get(k) for k in keep}, "eval_pm": round(o[s]["mp_net_less_fees"] / MON[s]), "usd500": vw[s]} for s in SP4}


def line(name, r):
    return f"{name:34s} {'PASS' if r['verdict']['pass'] else ('both' if r['verdict']['both'] else '    ')} ref {r['verdict']['ref']} | " + " | ".join(
        f"{s} 2w {r['o'][s]['p10']}/{r['o'][s]['dead10']} ${r['o'][s]['eval_pm']}/mo R {r['o'][s]['usd500']['r_per_risk']:+.3f} n{r['o'][s]['usd500']['n']}"
        for s in SP4)


# ================================================================================================ 1. windows
def cmd_windows():
    t0 = time.time()
    V2, A, M, EAB = E.atlas_libs()
    V0 = V2.V_()
    base = E.a_score(V0)
    U = A.account_units(V0)
    sp_of = np.array([D.a_span(u["day"]) for u in U])
    R = np.array([D.aR(u) for u in U])
    MU = {nm: M.units()[nm] for nm in MEMBERS}
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "today": compact(base, view(U, sp_of)), "fams": {}}
    print(line("ATLAS today", {"o": out["today"], "verdict": {"pass": False, "both": False, "ref": "="}}), flush=True)

    def run(drops):
        """drops: {member: set of buckets} in family fam (set per call) -> scored variant."""
        dr = {nm: [u["entry_t"] for u in MU[nm] if bucket(u, fam) in bs] for nm, bs in drops.items() if bs}
        V = V2.V_(drop=dr)
        o = E.a_score(V)
        UU = A.account_units(V)
        so = np.array([D.a_span(u["day"]) for u in UU])
        return {"o": compact(o, view(UU, so)), "verdict": V2.verdict(o, base)}

    def per_year(nm, b):
        k = [i for i, u in enumerate(U) if u["src"] == nm and bucket(u, fam) == b]
        yrs = collections.defaultdict(list)
        for i in k:
            d = U[i]["day"]
            yrs[d[:4] if d < "2026-01-01" else ("2026H1" if d < "2026-07-01" else "2026H2")].append(R[i])
        return {y: [len(v), round(float(np.sum(v)), 2)] for y, v in sorted(yrs.items())}

    for fam in FAMS:
        F = {"picks": {}, "rows": {}}
        h1b = {}
        for nm in MEMBERS:
            k = [(bucket(u, fam), R[i]) for i, u in enumerate(U) if u["src"] == nm and sp_of[i] == "H1"]
            agg = collections.defaultdict(list)
            for b, r in k:
                agg[b].append(r)
            h1b[nm] = sorted(agg)
            cand = [(float(np.sum(v)), b) for b, v in agg.items() if len(v) >= 3 and np.sum(v) < 0]
            if cand:
                tot, b = min(cand)
                F["picks"][nm] = {"bucket": b, "label": blabel(b, fam), "h1_n": len(agg[b]), "h1_R": round(tot, 2), "per_year": per_year(nm, b)}
            else:
                F["picks"][nm] = None
            print(fam, nm, F["picks"][nm], flush=True)
        picks = {nm: p["bucket"] for nm, p in F["picks"].items() if p}
        for nm, b in picks.items():
            F["rows"][f"{nm} skip {blabel(b, fam)}"] = run({nm: {b}})
            for nb in ((b - 1) % 7, (b + 1) % 7) if fam == "dow" else (b - 1, b + 1):
                F["rows"][f"{nm} skip {blabel(nb, fam)} (neighbour)"] = r = run({nm: {nb}})
                r["per_year"] = per_year(nm, nb)
        if len(picks) > 1:
            F["rows"]["all picks"] = run({nm: {b} for nm, b in picks.items()})
        for k, r in F["rows"].items():
            print(line(f"{fam} {k}", r), flush=True)
        # random-window controls: a random H1 bucket with trades per member (same members as the picks)
        rng = np.random.default_rng(31)
        pl = []
        for s in range(N_PL):
            drops = {nm: {int(rng.choice(h1b[nm]))} for nm in picks}
            r = run(drops)
            pl.append({"drops": {nm: list(v) for nm, v in drops.items()}, "pass": r["verdict"]["pass"], "both": r["verdict"]["both"],
                       **{s: (r["o"][s]["eval_pm"], r["o"][s]["usd500"]["r_per_risk"]) for s in SP4}})
        F["placebo_n"] = N_PL
        F["placebo_pass_share"] = round(float(np.mean([p["pass"] for p in pl])), 3)
        F["placebo_both_share"] = round(float(np.mean([p["both"] for p in pl])), 3)
        ref = F["rows"].get("all picks") or (next(iter(F["rows"].values())) if F["rows"] else None)
        if ref:
            F["placebo_rank"] = {s: {"p_eval": round(float(np.mean([p[s][0] >= ref["o"][s]["eval_pm"] for p in pl])), 3),
                                     "p_R": round(float(np.mean([p[s][1] >= ref["o"][s]["usd500"]["r_per_risk"] - 1e-9 for p in pl])), 3),
                                     "pl_mean_eval": round(float(np.mean([p[s][0] for p in pl])))} for s in SP4}
        F["placebo"] = pl
        print(fam, "placebo pass", F["placebo_pass_share"], "both", F["placebo_both_share"], json.dumps(F.get("placebo_rank")), f"{time.time() - t0:.0f}s", flush=True)
        out["fams"][fam] = F
    E.dump(out, OUT_W)
    print(f"wrote {OUT_W} {time.time() - t0:.0f}s", flush=True)
    return out


def cmd_singles(fam="m30"):
    """every single-bucket cut (each member x each bucket with a 2026 H1 trade): how many pass the v2 test by chance, and the
    H1 trades inside the picked bucket (entry times) -> research/second/atw_singles_<fam>.json"""
    t0 = time.time()
    V2, A, M, EAB = E.atlas_libs()
    V0 = V2.V_()
    base = E.a_score(V0)
    U = A.account_units(V0)
    MU = {nm: M.units()[nm] for nm in MEMBERS}
    rows = []
    for nm in MEMBERS:
        bs = sorted({bucket(u, fam) for u in U if u["src"] == nm and D.a_span(u["day"]) == "H1"})
        for b in bs:
            dr = {nm: [u["entry_t"] for u in MU[nm] if bucket(u, fam) == b]}
            V = V2.V_(drop=dr)
            o = E.a_score(V)
            v = V2.verdict(o, base)
            h1 = [(u["day"], A.et_mod(u["entry_t"]), round(D.aR(u), 2)) for u in U if u["src"] == nm and bucket(u, fam) == b and D.a_span(u["day"]) == "H1"]
            rows.append({"member": nm, "bucket": b, "label": blabel(b, fam), "verdict": v, "h1_trades": h1,
                         **{s: {"p10": o[s]["p10"], "dead10": o[s]["dead10"], "eval_pm": round(o[s]["mp_net_less_fees"] / MON[s])} for s in SP4}})
            print(nm, blabel(b, fam), "PASS" if v["pass"] else ("both" if v["both"] else "    "), v["ref"],
                  " | ".join(f"{s} {o[s]['p10']}/{o[s]['dead10']} ${round(o[s]['mp_net_less_fees'] / MON[s])}" for s in SP4), h1 if v["pass"] else "", flush=True)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "fam": fam, "n": len(rows), "n_pass": sum(r["verdict"]["pass"] for r in rows),
           "n_both": sum(r["verdict"]["both"] for r in rows), "rows": rows}
    E.dump(out, os.path.join(ROOT, "research", "second", f"atw_singles_{fam}.json"))
    print(f"{out['n']} single cuts, {out['n_pass']} pass, {out['n_both']} better in both halves; {time.time() - t0:.0f}s", flush=True)
    return out


# ================================================================================================ 2. limit entries
def _spec_for(spec, X, risk0, risk1, shift):
    """mg "r" (default): the member's management in R of the actual fill (BE at +1R of the new, smaller risk); mg "price":
    the same PRICE levels as the market entry (BE trigger at market entry + 1R, 15-minute check levels unchanged)."""
    if X.get("mg", "r") != "price" or risk1 <= 0:
        return spec
    sp = dict(spec)
    if sp.get("be_r") is not None:
        sp["be_r"] = (sp["be_r"] * risk0 + shift) / risk1
    if sp.get("tcheck"):
        n, x, y = sp["tcheck"]
        sp["tcheck"] = (n, (x * risk0 - shift) / risk1, (y * risk0 + shift) / risk1)
    return sp


def entry_units(X, stats=None):
    """the members' units with the entry rule X = {"px": mid|q25|q50, "wait": minutes, "else": skip|mkt}."""
    from tools import structure_atlas as SA
    V2, A, M, EAB = E.atlas_libs()
    U0 = M.units()
    P = SA.prices()
    B5 = SA.RX.cx()[300].B
    out = {k: list(v) for k, v in U0.items()}
    st = collections.Counter() if stats is None else stats
    det = []
    for src in MEMBERS:
        new = []
        for u in U0[src]:
            t = P.get((src, int(u["entry_t"]), int(u["dir"])))
            rows, secs = SA.rows_for(u) if t is not None else (None, None)
            if not rows:
                st["no_bars"] += 1
                new.append(u)
                continue
            d = int(u["dir"])
            entry, stop, target = float(t["entry"]), float(t["stop"]), float(t["target"])
            spec = SA.SPECS[src]
            risk0 = (entry - stop) * d
            if risk0 <= 0:
                new.append(u)
                continue
            if X["px"] == "mid":
                j = int(np.searchsorted(B5.t, int(u["entry_t"]) - 300))
                if j >= B5.n or int(B5.t[j]) != int(u["entry_t"]) - 300:
                    new.append(u); st["no_sig_bar"] += 1
                    continue
                L = (float(B5.h[j]) + float(B5.l[j])) / 2.0
                if (entry - L) * d < TICK:              # not better than the market entry: the market entry stays
                    new.append(u); st["mid_not_better"] += 1
                    continue
            else:
                L = entry - d * float(X["px"][1:]) / 100.0 * risk0     # q0 = at the market entry (executor check)
            L = round(L * 4) / 4.0
            base = SA._walk_secs(rows, secs, d, entry, stop, target, spec)
            nwait = max(1, int(round(X["wait"] * 60 / secs)))
            fill, k, gone = None, None, False
            for i in range(min(nwait, len(rows))):
                _, o, h, l, c = rows[i]
                od, hd, ld = (o, h, l) if d == 1 else (-o, -l, -h)
                if ld <= L * d - TICK:
                    fill, k = min(L * d, od) * d, i
                    break
                if hd >= target * d:
                    gone = True
                    break
            st["all"] += 1
            if fill is None:
                if X["else"] == "skip" or gone or nwait >= len(rows):
                    st["skipped"] += 1
                    det.append({"src": src, "day": u["day"], "pts": u["pts"], "R": D.aR(u), "filled": False})
                    continue                                  # the trade is not taken
                k = nwait
                fill = float(rows[k][1]) + d * TICK            # market at the next bar's open + 1 tick
                if (fill - stop) * d <= TICK or (target - fill) * d <= 0:
                    st["skipped"] += 1
                    det.append({"src": src, "day": u["day"], "pts": u["pts"], "R": D.aR(u), "filled": False})
                    continue
                st["late_mkt"] += 1
                r1 = (fill - stop) * d
                alt = SA._walk_secs(rows[k:], secs, d, fill, stop, target, _spec_for(spec, X, risk0, r1, (entry - fill) * d))
            else:
                st["filled"] += 1
                _, o, h, l, c = rows[k]
                ld = l if d == 1 else -h
                if ld <= stop * d:
                    alt = {"pts": round(stop * d - TICK - fill * d, 4), "kind": "STOP", "t_exit": int(rows[k][0]) + secs}
                elif k + 1 >= len(rows):
                    alt = {"pts": round((c if d == 1 else -c) - TICK - fill * d, 4), "kind": "EOD", "t_exit": int(rows[k][0]) + secs}
                else:
                    r1 = (fill - stop) * d
                    alt = SA._walk_secs(rows[k + 1:], secs, d, fill, stop, target, _spec_for(spec, X, risk0, r1, (entry - fill) * d))
            pts = u["pts"] + (alt["pts"] - base["pts"])
            risk1 = (fill - stop) * d
            shift = (entry - fill) * d
            w1 = min(0.0, u["w1"] + shift)
            if alt["kind"] == "STOP":
                w1 = min(w1, pts)
            w1 = max(-(risk1 + TICK), w1)
            nu = {**u, "entry_t": int(rows[k][0]), "risk": round(risk1, 4), "tgt": round((target - fill) * d, 4), "pts": round(pts, 4), "w1": round(w1, 4),
                  "exit": alt["kind"], "exit_t": int(alt["t_exit"] or u["exit_t"]), "po": u["po"] + shift, "pw": np.maximum(u["pw"] + shift, -(risk1 + TICK))}
            det.append({"src": src, "day": u["day"], "pts": u["pts"], "R": D.aR(u), "filled": True, "R_new": D.aR(nu), "late": fill is not None and k == nwait and X["else"] == "mkt"})
            new.append(nu)
        out[src] = new
    return out, det


def score_units(UU):
    V2, A, M, EAB = E.atlas_libs()
    saved = M._UC["u"]
    M._UC["u"] = UU
    try:
        V = V2.V_()
        o = E.a_score(V)
        AU = A.account_units(V)
    finally:
        M._UC["u"] = saved
    so = np.array([D.a_span(u["day"]) for u in AU])
    return o, AU, so


def entry_specs():
    out = [("limit q0 15m else skip (executor check)", {"px": "q0", "wait": 15, "else": "skip"}),
           ("limit q0 15m else skip (executor check, price mgmt)", {"px": "q0", "wait": 15, "else": "skip", "mg": "price"})]
    for mg in ("r", "price"):
        for px in ("mid", "q25", "q50"):
            for w in (15, 30):
                for el in ("skip", "mkt"):
                    out.append((f"limit {px} {w}m else {el}" + (" (price mgmt)" if mg == "price" else ""), {"px": px, "wait": w, "else": el, "mg": mg}))
    return out


def cmd_entries():
    t0 = time.time()
    V2, A, M, EAB = E.atlas_libs()
    base_o = E.a_score(V2.V_())
    U0 = A.account_units(V2.V_())
    so0 = np.array([D.a_span(u["day"]) for u in U0])
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "today": compact(base_o, view(U0, so0)), "rows": {}}
    # entry slippage of the stored research entries vs the 5m open (for the record)
    from tools import structure_atlas as SA
    P = SA.prices()
    B5 = SA.RX.cx()[300].B
    sl = []
    for (src, et, d), t in P.items():
        j = int(np.searchsorted(B5.t, et))
        if j < B5.n and int(B5.t[j]) == et:
            sl.append((float(t["entry"]) - float(B5.o[j])) * d)
    out["stored_entry_minus_open_ticks"] = {"median": round(float(np.median(sl)) / TICK, 2), "mean": round(float(np.mean(sl)) / TICK, 2), "n": len(sl)}
    print("stored entry - 5m open (ticks):", out["stored_entry_minus_open_ticks"], f"{time.time() - t0:.0f}s", flush=True)
    for name, X in entry_specs():
        if X is None:
            continue
        st = collections.Counter()
        UU, det = entry_units(X, st)
        o, AU, so = score_units(UU)
        r = {"X": X, "o": compact(o, view(AU, so)), "verdict": V2.verdict(o, base_o), "stats": dict(st)}
        # fill rate, missed winners vs saved losers (member research units, per span)
        sp = {}
        for s in SP4:
            dd = [x for x in det if D.a_span(x["day"]) == s]
            nf = [x for x in dd if not x["filled"]]
            fl = [x for x in dd if x["filled"]]
            sp[s] = {"n": len(dd), "fill_rate": round(100.0 * len(fl) / max(1, len(dd)), 1),
                     "missed_winners": [sum(1 for x in nf if x["R"] > 0), round(sum(x["R"] for x in nf if x["R"] > 0), 2)],
                     "saved_losers": [sum(1 for x in nf if x["R"] <= 0), round(sum(x["R"] for x in nf if x["R"] <= 0), 2)],
                     "filled_R_old": round(sum(x["R"] for x in fl), 2), "filled_R_new": round(sum(x["R_new"] for x in fl), 2)}
        r["fills"] = sp
        out["rows"][name] = r
        print(line(name, r), "| fills", {s: (sp[s]["fill_rate"], sp[s]["missed_winners"], sp[s]["saved_losers"]) for s in SP4}, f"{time.time() - t0:.0f}s", flush=True)
    E.dump(out, OUT_E)
    print(f"wrote {OUT_E} {time.time() - t0:.0f}s", flush=True)
    return out


# ================================================================================================ run library
def _vline(r, today):
    return "; ".join(f"{s} 2-week pass/dead {r['o'][s]['p10']}/{r['o'][s]['dead10']} (today {today[s]['p10']}/{today[s]['dead10']}), eval paths "
                     f"${r['o'][s]['eval_pm']}/mo (today ${today[s]['eval_pm']}), R/risk {r['o'][s]['usd500']['r_per_risk']:+.3f} (today "
                     f"{today[s]['usd500']['r_per_risk']:+.3f})" for s in SP4)


WHY = {
    "atw_win_m30": "The combined cut fails the 2021-24 tier (-$67 vs -$36 a month).",
    "atw_win_m30_sr": ("Rejected: it is the S/R 11:00 spike of atlas.md (the 3 H1 trades all entered at 11:00 and stopped out), both neighbours "
                       "fail, and 3 of all 25 single 30-minute cuts pass the same test (research/second/atw_singles_m30.json)."),
    "atw_win_m60": "H2 eval-path $ is lower than today (fails H2).",
    "atw_win_dow": ("Rejected: neither weekday cut passes alone, every neighbour fails, the skipped S/R Wednesday trades made +10.3R in "
                    "2021-25, and weekday rules are what calendar-effects.md / atlas.md already found to be chance."),
}
SAVE_ENTRIES = ("limit mid 30m else skip", "limit mid 30m else mkt", "limit q25 30m else skip", "limit q25 30m else mkt",
                "limit q50 30m else skip", "limit q50 30m else mkt", "limit q0 15m else skip (executor check)")


def cmd_save(entry_names=SAVE_ENTRIES):
    from tools import runlib as rl
    V2, A, M, EAB = E.atlas_libs()
    sess = sorted(set(M.units()["sessions"]))
    W = json.load(open(OUT_W, encoding="utf-8"))
    EN = json.load(open(OUT_E, encoding="utf-8"))
    MU = {nm: M.units()[nm] for nm in MEMBERS}
    for fam in FAMS:
        F = W["fams"][fam]
        picks = {nm: p["bucket"] for nm, p in F["picks"].items() if p}
        if not picks:
            continue
        sets = [("all picks", picks, f"atw_win_{fam}")] if "all picks" in F["rows"] else []
        # a single-member pick that passes the v2 test on its own is stored too (e.g. m30 SR no 11:00-11:30)
        for nm, b in picks.items():
            k = f"{nm} skip {blabel(b, fam)}"
            if F["rows"][k]["verdict"]["pass"] or not sets:
                sets.append((k, {nm: b}, f"atw_win_{fam}" if not sets else f"atw_win_{fam}_{nm.lower()}"))
        for key, pk, rid in sets:
            r = F["rows"][key]
            dr = {nm: [u["entry_t"] for u in MU[nm] if bucket(u, fam) == b] for nm, b in pk.items()}
            o, T = E._atlas_store(V2.V_(drop=dr))
            what = ", ".join(f"{nm} no {F['picks'][nm]['label']}" for nm in pk)
            st = "rejected"
            why = WHY.get(rid, "")
            vt = (f"Per-member window cut picked on 2026 H1 ({fam}: {what}): {_vline(r, W['today'])}. v2 test: {'passes' if r['verdict']['pass'] else 'fails'}; "
                  f"random windows pass it {F['placebo_pass_share'] * 100:.0f}% of the time ({F['placebo_n']} draws). {why}")
            rl.save(rid, f"ATLAS per-member window cut ({fam}: {what}) - {st}", "timing",
                    "Owner 2026-10-30: skip each ATLAS member's weakest time-of-day / weekday window?",
                    params={"family": fam, "picks": {nm: F["picks"][nm] for nm in pk}}, sizing={"account_b": "need size (engine/account_b.qty)"}, trades=T,
                    scored=rl.score(T, sess), status=st, verdict=vt, notes="tools/atw_atlas.py windows (eval-path trades, 4 spans)",
                    writeup="atlas-windows-entries-2026-10-30", tags=["atlas", "account_b", "25k", "timing"])
            print("saved", rid, flush=True)
    names = entry_names or list(EN["rows"])
    for name in names:
        r = EN["rows"][name]
        X = r["X"]
        UU, _ = entry_units(X)
        saved = M._UC["u"]
        M._UC["u"] = UU
        try:
            o, T = E._atlas_store(V2.V_())
        finally:
            M._UC["u"] = saved
        rid = f"atw_entry_{X['px']}_{X['wait']}m_{X['else']}" + ("_pm" if X.get("mg") == "price" else "")
        st = "info" if X["px"] == "q0" else ("rejected" if not r["verdict"]["pass"] else "promising")
        fr = r["fills"]
        vt = (f"ATLAS {name}: fill rate {' / '.join(str(fr[s]['fill_rate']) for s in SP4)}% (H1 / H2 / 2025 / 2021-24); {_vline(r, EN['today'])}. "
              f"v2 test: {'passes' if r['verdict']['pass'] else 'fails'}.")
        rl.save(rid, f"ATLAS entry: {name} - {st}", "other", "Owner 2026-10-30: enter ATLAS with a limit at a better price instead of market at the next open?",
                params={"entry": X}, sizing={"account_b": "need size on the (smaller) limit-fill risk"}, trades=T, scored=rl.score(T, sess), status=st,
                verdict=vt, notes="tools/atw_atlas.py entries (difference method, 1m 2026 / 5m before)", writeup="atlas-windows-entries-2026-10-30",
                tags=["atlas", "account_b", "25k", "entry"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "windows"
    {"windows": cmd_windows, "entries": cmd_entries, "singles": cmd_singles, "save": cmd_save}[cmd]()
