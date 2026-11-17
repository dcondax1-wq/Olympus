"""ATLAS revive (2026-11-17, night-atlas): ATLAS (account B: EMA + MACD + S/R) carries the owner's FUNDED 25K, and the edge-health
check found it weak lately (stored run atlas_deep_zombie, last 40 sessions to Oct 16: PF 1.41, ~$411 a month vs a 2026 median
PF 2.8). Which member / condition is fading, and does a member weight / drop / add from the existing candidate pool fix it?

Research only: nothing here touches second_model.json, data/account_b.json, live_model*.json or any engine file.

  python -X utf8 tools/atlas_revive.py diag      # fade autopsy -> research/second/atlas_revive_diag.json
  python -X utf8 tools/atlas_revive.py fixes     # weights / drops / adds on the funded 25K -> research/second/atlas_revive.json
  python -X utf8 tools/atlas_revive.py placebo   # random-skip control of the VIX lead -> atlas_revive_placebo.json
  python -X utf8 tools/atlas_revive.py all

Trades: the live ATLAS units (tools/atlas.account_units: never opposite LIT incl. its armed setups, HEDGE close), then ATLAS's
one position + max 2 a day (= tools/money/stack_one_account._atlas). R per trade at a fixed risk, costs in ($1.90 a micro,
the unit's pts carry the slippage; tools/atlas_deep.r_net). Freshest data: the members' own PC paper trades Oct 19 - Nov 6
(heartbeat branch heartbeat.json "second"), shown next to the stored history (the cloud has no member re-run on PC bars).
Funded 25K money: tools/money/builder_levers.funded_run on the same Monte Carlo paths as funded25.py (engine/funded_life
builder25k, MFFU rules, 600 paths x 126 sessions, 5-session blocks), member weights applied the way engine/account_b.funded_qty
does (micros x w, min 1, never above the funded preset).
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
from tools import atlas as A  # noqa: E402
from tools import second_mix as M  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT_DIAG = os.path.join(ROOT, "research", "second", "atlas_revive_diag.json")
OUT = os.path.join(ROOT, "research", "second", "atlas_revive.json")
SP = {"2026 H1": ("2026-01-01", "2026-06-30"), "Jul-Aug": ("2026-07-01", "2026-08-31"), "Sep-Oct16": ("2026-09-01", "2026-10-16"),
      "2025": ("2025-01-01", "2025-12-31"), "2021-24": ("2021-01-01", "2024-12-31")}
VIXB = ((0, 15, "<15"), (15, 18, "15-18"), (18, 22, "18-22"), (22, 99, "22+"))
HB_KEYS = {"ema_lon_vix": "EMA", "macd_sweep": "MD", "sr_nyreclaim": "SR", "sh_asia": "SHA", "sh_trend": "SHT"}


# ================================================================================================ trades + facts
def one_pos(U):
    """ATLAS's own one position + max 2 a day (engine/account_b), in entry order."""
    out, cur, busy, nday = [], None, 0, 0
    for t in sorted(U, key=lambda t: t["entry_t"]):
        if t["day"] != cur:
            cur, busy, nday = t["day"], 0, 0
        if t["entry_t"] < busy or nday >= 2:
            continue
        busy, nday = t["exit_t"], nday + 1
        out.append(t)
    return out


def r_net(u):
    return (u["pts"] * M.PV - M.ECOMM) / (u["risk"] * M.PV)


_C = {}


def day_er():
    """day -> RTH trend efficiency |close - open| / sum |5m moves| (09:30-16:00 ET) from the 5m NQ1! bars."""
    if "er" not in _C:
        from tools import atlas_deep as D
        B = D.bars5()
        mods = np.array([(dt.datetime.fromtimestamp(int(t), ET).hour * 60 + dt.datetime.fromtimestamp(int(t), ET).minute) for t in B.t])
        days = np.array([dt.datetime.fromtimestamp(int(t), ET).date().isoformat() for t in B.t])
        er = {}
        rth = (mods >= 570) & (mods < 960)
        for d in np.unique(days[rth]):
            k = np.where(rth & (days == d))[0]
            if len(k) < 30:
                continue
            path = float(np.abs(np.diff(np.r_[B.o[k[0]], B.c[k]])).sum())
            er[str(d)] = abs(float(B.c[k[-1]] - B.o[k[0]])) / path if path > 0 else 0.0
        _C["er"] = er
    return _C["er"]


def facts(t, vix, er, trend, sess_idx, sess):
    x = dt.datetime.fromtimestamp(int(t["entry_t"]), ET)
    v = vix.get(t["day"], float("nan"))
    vb = next((n for a, b, n in VIXB if a <= v < b), "na")
    i = sess_idx.get(t["day"])
    prev = sess[i - 1] if i else None
    e0, ep = er.get(t["day"]), er.get(prev)
    return {"member": t["src"], "side": "long" if t["dir"] > 0 else "short", "member_side": f"{t['src']} {'L' if t['dir'] > 0 else 'S'}",
            "hour": f"{x.hour:02d}", "vix": vb,
            "day_type": "na" if e0 is None else ("trend" if e0 >= 0.35 else ("chop" if e0 < 0.15 else "mixed")),
            "prev_day_type": "na" if ep is None else ("trend" if ep >= 0.35 else ("chop" if ep < 0.15 else "mixed")),
            "with_daily_trend": "with" if trend.get(t["day"], 0) * t["dir"] > 0 else "against",
            "exit": str(t.get("exit", "?")).upper()}


def span_of(d):
    for k, (a, z) in SP.items():
        if a <= d <= z:
            return k
    return None


def stats(rs):
    r = np.asarray(rs, float)
    if not len(r):
        return {"n": 0}
    gw, gl = r[r > 0].sum(), -r[r < 0].sum()
    return {"n": int(len(r)), "avg_r": round(float(r.mean()), 3), "sum_r": round(float(r.sum()), 2),
            "win": round(100 * float((r > 0.05).mean()), 1), "pf": round(float(gw / gl), 2) if gl > 0 else None}


def heartbeat_trades():
    """The members' own paper trades as the PC's live loop logged them (heartbeat branch, last push 2026-11-07)."""
    try:
        raw = subprocess.run(["git", "-C", ROOT, "show", "origin/heartbeat:heartbeat.json"], capture_output=True, timeout=60).stdout
        h = json.loads(raw)
    except Exception:
        return []
    out = []
    for k, v in ((h.get("second") or {}).get("strategies") or {}).items():
        for t in v.get("trades") or []:
            if t.get("day", "") > "2026-10-16" and t.get("r") is not None and t.get("exit_kind") != "OPEN":
                out.append({"src": HB_KEYS.get(k, k), "day": t["day"], "dir": int(t["dir"]), "r": float(t["r"]),
                            "exit": t.get("exit_kind"), "entry_t": int(t["entry_t"])})
    return sorted(out, key=lambda t: t["entry_t"])


def cmd_diag(log=print):
    U = one_pos(A.account_units(A.BASE))
    sess = M.units()["sessions"]
    sidx = {d: i for i, d in enumerate(sess)}
    last40 = set(sess[-40:])
    vix, er = A.vix_prev(), day_er()
    from tools import atlas_deep as D
    trend = D.daily_trend()
    rows = []
    for t in U:
        f = facts(t, vix, er, trend, sidx, sess)
        f.update(day=t["day"], r=r_net(t), span=span_of(t["day"]), last40=t["day"] in last40)
        rows.append(f)
    dims = ("member", "side", "member_side", "hour", "vix", "day_type", "prev_day_type", "with_daily_trend", "exit")
    spans = list(SP) + ["last 40 (Aug 19-Oct 16)"]
    out = {"date": "2026-11-17", "last40": [sess[-40], sess[-1]], "n_units": len(rows), "tables": {}}

    def sel(sp):
        if sp.startswith("last 40"):
            return [x for x in rows if x["last40"]]
        return [x for x in rows if x["span"] == sp]
    out["overall"] = {sp: stats([x["r"] for x in sel(sp)]) for sp in spans}
    for dm in dims:
        tab = {}
        keys = sorted({x[dm] for x in rows})
        for k in keys:
            tab[k] = {sp: stats([x["r"] for x in sel(sp) if x[dm] == k]) for sp in spans}
        out["tables"][dm] = tab
    # the newest weeks: the PC's own member paper trades (each member's own ledger, before the account rules)
    hb = heartbeat_trades()
    out["pc_paper_oct19_nov6"] = {m: stats([t["r"] for t in hb if t["src"] == m]) for m in sorted({t["src"] for t in hb})}
    out["pc_paper_oct19_nov6"]["ATLAS 3 members"] = stats([t["r"] for t in hb if t["src"] in ("EMA", "MD", "SR")])
    out["pc_paper_trades"] = hb
    # monthly R by member (2026)
    mon = collections.defaultdict(lambda: collections.defaultdict(list))
    for x in rows:
        if x["day"] >= "2026-01-01":
            mon[x["day"][:7]][x["member"]].append(x["r"])
    out["monthly_2026"] = {m: {k: stats(v) for k, v in sorted(d.items())} | {"all": stats([r for v in d.values() for r in v])}
                           for m, d in sorted(mon.items())}
    with open(OUT_DIAG, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    log(f"wrote {os.path.relpath(OUT_DIAG, ROOT)}")
    show_diag(out, log)
    return out


def show_diag(o, log=print):
    sps = list(o["overall"])
    hdr = " " * 22 + "".join(f"{s[:13]:>22s}" for s in sps)
    log(hdr)

    def line(name, d):
        cells = []
        for s in sps:
            x = d.get(s) or {}
            cells.append(f"{x.get('n', 0):3d} {x.get('avg_r', 0) if x.get('n') else 0:+6.2f} pf{(x.get('pf') or 0):5.2f}  ")
        log(f"{name[:22]:22s}" + "".join(f"{c:>22s}" for c in cells))
    line("ALL", o["overall"])
    for dm, tab in o["tables"].items():
        log(f"-- {dm}")
        for k, d in tab.items():
            line(f"  {k}", d)
    log("-- PC paper Oct 19 - Nov 6 (members' own ledgers):")
    for k, v in o["pc_paper_oct19_nov6"].items():
        log(f"  {k:16s} {v}")
    log("-- monthly 2026 (all members, avg R / n):")
    for m, d in o["monthly_2026"].items():
        log(f"  {m} " + "  ".join(f"{k} {v['n']}x{v.get('avg_r', 0):+.2f}" for k, v in d.items()))


# ================================================================================================ fixes on the funded 25K
# Written down before the first funded run. Each: members, weights (funded: micros x w, min 1, never above the preset;
# engine/account_b "weights"), an optional account-wide prior-VIX rule. "post-hoc" = suggested by the diag above (which saw
# H2 and 2021-24), so its H2 is not a clean check; "re-measure" = already tested (round 3), shown on the same paths only.
IDEAS = {
    "ATLAS today": {},
    # 1. drop a member (dropping members was rejected on the EVAL path, atlas.md / atlas-v2.md; never scored funded)
    "drop S/R": {"members": ["EMA", "MD"]},
    "drop EMA": {"members": ["MD", "SR"]},
    "drop MACD": {"members": ["EMA", "SR"]},
    # 2. member weights down (rejected on the eval: "one winner passes" needs the full size; never scored funded)
    "S/R x0.5": {"w": {"SR": 0.5}},
    "S/R x0.75": {"w": {"SR": 0.75}},
    "EMA x0.5": {"w": {"EMA": 0.5}},
    "EMA x0.75": {"w": {"EMA": 0.75}},
    "MACD x0.5": {"w": {"MD": 0.5}},
    "MACD x0.75": {"w": {"MD": 0.75}},
    # 3. low-VIX days (post-hoc: VIX < 15 loses in every span in the diag; per-member VIX >= 14 / 16 gates were rejected
    #    on the eval in atlas.md, the funded per-member VIX terciles in atlas-funded-one-a-day)
    "skip VIX < 14": {"vix_skip": 14.0},
    "skip VIX < 15": {"vix_skip": 15.0},
    "skip VIX < 16": {"vix_skip": 16.0},
    "skip VIX < 14.5": {"vix_skip": 14.5},      # neighbours of the 15 cut, added after the first run (counted)
    "skip VIX < 15.5": {"vix_skip": 15.5},
    "half size VIX < 15": {"vix_half": 15.0},
    # 4. add from the candidate pool (re-measure: the hunts were scored funded in 2026-11-04_atlas_round3.md)
    "+ both hunts x0.5": {"members": ["EMA", "MD", "SR", "SHA", "SHT"], "w": {"SHA": 0.5, "SHT": 0.5}},
    "+ trend hunt x0.5": {"members": ["EMA", "MD", "SR", "SHT"], "w": {"SHT": 0.5}},
    # 5. combinations of the above, only if a single idea passes (filled in by cmd_fixes)
}
POST_HOC = {"skip VIX < 14", "skip VIX < 15", "skip VIX < 16", "skip VIX < 14.5", "skip VIX < 15.5", "half size VIX < 15"}
RE_MEASURE = {"+ both hunts x0.5", "+ trend hunt x0.5"}


def variant_units(I):
    """ATLAS's funded trades for idea I: members -> account_units (no-hedge vs LIT + armed) -> one position, max 2 a day."""
    from tools import atlas_v2 as V2
    if any(m in ("SHA", "SHT") for m in I.get("members", ())):
        V2.install()
    V = {**A.BASE, "members": list(I.get("members") or A.BASE["members"])}
    U = A.account_units(V)
    vix = A.vix_prev()
    if I.get("vix_skip"):
        U = [u for u in U if not (vix.get(u["day"], 99.0) < I["vix_skip"])]
    out = []
    for t in one_pos(U):
        w = float((I.get("w") or {}).get(t["src"], 1.0))
        if I.get("vix_half") and vix.get(t["day"], 99.0) < I["vix_half"]:
            w *= 0.5
        out.append({"day": t["day"], "risk": float(t["risk"]), "tgt": float(t["tgt"] or 0) or None, "pts": float(t["pts"]),
                    "w1": float(min(0.0, t["w1"])), "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]),
                    "strat": "ATLAS", "src": t["src"], "w": w})
    return out


def by_session(T, S):
    by = collections.defaultdict(list)
    for t in T:
        by[t["day"]].append(t)
    return [sorted(by.get(d, []), key=lambda t: t["entry_t"]) for d in S]


def fixed_stats(T, S, span, usd=250.0):
    """Every trade at $usd x its weight, costs in, the real days of the span in order."""
    from tools import uprisk as U
    a, z = U.SPAN[span]
    days = [d for d in S if a <= d <= z]
    ds = set(days)
    L = [t for t in T if t["day"] in ds]
    pnl = []
    for t in L:
        loss1 = (t["risk"] + M.SLIP) * M.PV + M.ECOMM
        q = int(usd * t["w"] // loss1)
        pnl.append(q * (t["pts"] * M.PV - M.ECOMM))
    p = np.array(pnl, float)
    eq = np.cumsum(p) if len(p) else np.zeros(1)
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    r = np.array([r_net(t) * t["w"] for t in L], float)
    return {"n": len(L), "tpw": round(len(L) / (len(days) / 5), 2), "pf": round(float(gw / gl), 2) if gl > 0 else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(days) / 21)),
            "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())) if len(p) else 0,
            "avg_r": round(float(r.mean()), 3) if len(r) else None}


def _wgf():
    import builder_levers as BL

    class WGF(BL.GF):
        """The funded 25K preset (engine/account_b.funded_qty) x the member weight: min 1, never above the preset."""

        def qty(self, t, st):
            q = super().qty(t, st)
            w = float(t.get("w", 1.0))
            if q > 0 and w != 1.0:
                q = min(q, max(1, int(q * w + 1e-9))) if w > 0 else 0
            return q
    return WGF


def shared_by(T, S):
    """LIT + ATLAS on one account (tools/money/funded25.atlas_shared on these ATLAS trades): an ATLAS entry while LIT holds
    is skipped, LIT entering closes ATLAS at market (second_mix.cut_at needs the path: rebuilt from the units)."""
    import stack_one_account as SA
    D = SA.data()
    lit = collections.defaultdict(list)
    for i, d in enumerate(D["S"]):
        for t in D["LIT"][i]:
            lit[d].append((int(t["entry_t"]), int(t["exit_t"])))
    keep = []
    for t in T:
        L = lit.get(t["day"], ())
        if any(a <= t["entry_t"] < z for a, z in L):
            continue
        nxt = min((a for a, _ in L if t["entry_t"] < a < t["exit_t"]), default=None)
        if nxt is not None:
            continue                       # conservative: a trade LIT would cut is dropped here (no path kept)
        keep.append(t)
    by = collections.defaultdict(list)
    for t in keep:
        by[t["day"]].append(t)
    pr = {"LIT": 0, "ATLAS": 1}
    return [sorted(list(D["LIT"][i]) + by.get(d, []), key=lambda t: (t["entry_t"], pr[t["strat"]])) for i, d in enumerate(D["S"])]


def passes(r, b):
    """Gate: funded $ a month to you better in BOTH 2026 halves (H1 pick, H2 check), no-payout and first payout not worse
    in either half, 2021-25 $ not lower (shown), 2-4 trades a week on the account in 2026 (today's ATLAS already trades
    4.06 a week in Jan-Jun, so the top is max(4, today's + 0.1): a fix may not add trades past the rule)."""
    ok = all(r[s]["funded"]["per_month"] > b[s]["funded"]["per_month"] for s in ("H1", "H2"))
    ok &= all(r[s]["funded"]["no_pay_6m"] <= b[s]["funded"]["no_pay_6m"] + 0.5 for s in ("H1", "H2"))
    ok &= all((r[s]["funded"]["first_med"] or 999) <= (b[s]["funded"]["first_med"] or 999) for s in ("H1", "H2"))
    ok &= r["REF"]["funded"]["per_month"] >= b["REF"]["funded"]["per_month"]
    ok &= all(2.0 <= r[s]["fixed"]["tpw"] <= max(4.0, b[s]["fixed"]["tpw"] + 0.1) for s in ("H1", "H2"))
    return bool(ok)


def cmd_fixes(n=600, log=print):
    import logging
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    import builder_levers as BL
    import stack_one_account as SA
    from tools import uprisk as U
    WGF = _wgf()
    S = SA.data()["S"]
    PF = {sp: U.mc_paths(S, sp, n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    sess = M.units()["sessions"]
    last40 = sess[-40:]
    hb = heartbeat_trades()
    out = {"date": "2026-11-17", "n": n, "spans": U.SPAN, "rows": {}, "gate": passes.__doc__.strip()}

    def score(nm, I, shared=False):
        T = variant_units(I)
        BY = shared_by(T, S) if shared else by_session(T, S)
        z = {"ATLAS": ("fq", None)} if not shared else {"LIT": ("fq", None), "ATLAS": ("stack", 250.0, 0.3)}
        row = {}
        for sp in BL.SPANS:
            f = BL.funded_run(BY, PF[sp], lambda z=z: WGF("builder25k", U.UP25, z))
            row[sp] = {"funded": f, "fixed": fixed_stats(T, S, sp)}
        L40 = [t for t in T if t["day"] >= last40[0]]
        row["last40"] = {"n": len(L40), "avg_r": round(float(np.mean([r_net(t) * t["w"] for t in L40])), 3) if L40 else None,
                         "sum_r": round(float(sum(r_net(t) * t["w"] for t in L40)), 2)}
        mem = set(I.get("members") or A.BASE["members"])
        P = [t for t in hb if t["src"] in mem]
        row["pc_paper"] = {"n": len(P), "sum_r": round(sum(t["r"] * float((I.get("w") or {}).get(t["src"], 1.0)) for t in P), 2)}
        return row

    def show(nm, r, tag=""):
        f = " | ".join(f"{sp} ${r[sp]['funded']['per_month']}/mo 1st {r[sp]['funded']['first_med']} nopay {r[sp]['funded']['no_pay_6m']}%"
                       for sp in BL.SPANS)
        x = " | ".join(f"{sp} {r[sp]['fixed']['tpw']}/wk PF {r[sp]['fixed']['pf']}" for sp in BL.SPANS)
        log(f"{nm:22s}{tag:4s} {f}\n{'':26s} {x} | last40 {r['last40']['sum_r']:+.1f}R pc {r['pc_paper']['sum_r']:+.1f}R")

    for nm, I in IDEAS.items():
        r = score(nm, I)
        out["rows"][nm] = {"idea": I, **r}
        tag = "" if nm == "ATLAS today" else (" ok" if passes(r, out["rows"]["ATLAS today"]) else "  -")
        out["rows"][nm]["passes"] = tag.strip() == "ok"
        out["rows"][nm]["kind"] = "post-hoc" if nm in POST_HOC else ("re-measure" if nm in RE_MEASURE else "pre-declared")
        show(nm, r, tag)
    base = out["rows"]["ATLAS today"]
    single = [nm for nm, r in out["rows"].items() if r.get("passes") and nm not in RE_MEASURE]
    out["single_passers"] = single
    # combinations: only of single passers (two at a time)
    combo = {}
    for i, a in enumerate(single):
        for b in single[i + 1:]:
            Ia, Ib = IDEAS[a], IDEAS[b]
            if "members" in Ia and "members" in Ib:
                continue
            I = {**Ia, **Ib, "w": {**(Ia.get("w") or {}), **(Ib.get("w") or {})}}
            combo[f"{a} + {b}"] = I
    for nm, I in combo.items():
        r = score(nm, I)
        out["rows"][nm] = {"idea": I, **r, "passes": passes(r, base), "kind": "combination"}
        show(nm, r, " ok" if out["rows"][nm]["passes"] else "  -")
    # the shared account (LIT + ATLAS $250 on the funded 25K, built OFF in engine/lit25.py) for today + every passer
    out["shared"] = {}
    for nm in ["ATLAS today"] + [k for k, r in out["rows"].items() if r.get("passes")]:
        I = out["rows"][nm]["idea"]
        r = score(nm, I, shared=True)
        out["shared"][nm] = r
        show("LIT+$250: " + nm, r)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    log(f"wrote {os.path.relpath(OUT, ROOT)}")
    return out


def cmd_placebo(name="skip VIX < 15", draws=40, n=300, log=print):
    """Random day skips that drop the same number of ATLAS trades per span as idea `name` (seeded): how often does chance
    lift the funded $ in both 2026 halves by at least as much?"""
    import logging
    import random
    logging.getLogger("engine.sizing").setLevel(logging.ERROR)
    import builder_levers as BL
    import stack_one_account as SA
    from tools import uprisk as U
    WGF = _wgf()
    S = SA.data()["S"]
    PF = {sp: U.mc_paths(S, sp, n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    base = variant_units({})
    rule = variant_units(IDEAS[name])
    kept = {t["entry_t"] for t in rule}

    def fund(T):
        BY = by_session(T, S)
        return {sp: BL.funded_run(BY, PF[sp], lambda: WGF("builder25k", U.UP25, {"ATLAS": ("fq", None)}))["per_month"] for sp in BL.SPANS}
    b, r = fund(base), fund(rule)
    gain = {sp: r[sp] - b[sp] for sp in BL.SPANS}
    log(f"{name}: today {b} rule {r} gain {gain}")
    sp_of = {}
    for t in base:
        for sp, (a, z) in U.SPAN.items():
            if a <= t["day"] <= z:
                sp_of[t["entry_t"]] = sp
    need = collections.Counter(sp_of.get(t["entry_t"]) for t in base if t["entry_t"] not in kept)
    log(f"trades the rule skips per span: {dict(need)}")
    rng = random.Random(20261117)
    res, hits = [], 0
    for k in range(draws):
        drop = set()
        for sp, cnt in need.items():
            pool = [t["entry_t"] for t in base if sp_of.get(t["entry_t"]) == sp]
            drop |= set(rng.sample(pool, cnt)) if sp else set()
        g = fund([t for t in base if t["entry_t"] not in drop])
        g = {sp: g[sp] - b[sp] for sp in BL.SPANS}
        res.append(g)
        hits += int(g["H1"] >= gain["H1"] and g["H2"] >= gain["H2"])
    out = {"idea": name, "gain": gain, "draws": res, "hit_rate": round(hits / draws, 3), "n_paths": n,
           "skipped_per_span": dict(need)}
    log(f"random skips as good in both halves: {hits}/{draws}; H2 gains p50 {np.median([g['H2'] for g in res]):+.0f} "
        f"p90 {np.percentile([g['H2'] for g in res], 90):+.0f}")
    p = os.path.join(ROOT, "research", "second", "atlas_revive_placebo.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("diag", "fixes", "placebo", "all"))
    ap.add_argument("--n", type=int, default=600)
    a = ap.parse_args(argv)
    t0 = time.time()
    if a.cmd in ("diag", "all"):
        cmd_diag()
    if a.cmd in ("fixes", "all"):
        cmd_fixes(a.n)
    if a.cmd in ("placebo", "all"):
        cmd_placebo()
    print(f"{time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
