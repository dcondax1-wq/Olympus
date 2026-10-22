"""Bad-market brake for account B (owner 2026-10-22, pre-launch job 3): in 2025 and 2021-24 about 35-39% of account B
evals are dead (failed or stuck) within 2 weeks. Can a simple rule that only looks back fix that without costing 2026?

Executor = tools/second_account_b.py (EMA + MACD + S/R on their own MFFU account, need size = engine/account_b.qty, max 2
a day, one position, the plan's soft daily loss, no hedge vs LIT, stuck = room under $100 ends the eval), plus one brake:

  streakN      size x0.5 after N losses in a row (the three strategies' own trades, in exit order; until the next win)
  sumK         size x0.5 while the last K trades (all three strategies) sum <= 0R
  sumK_skip    no trade while the last K trades sum <= 0R
  wkX          no trade for the rest of the calendar week once that week's trades sum <= -X R
  wkX_half     half size for the rest of the week instead
  vxnA-B       size x0.5 when the prior day's VXN close is outside [A, B) (CBOE file, known before the session)
  vixA-B       the same on VIX
  fit          the "stuck" rule as "1 micro must fit": no eval end at $100 of room; a trade is skipped only when a
               1-micro stop-out (stop + 2 ticks, $1.90) does not fit in the room (the eval stays alive for small stops)
The brake history is the strategies' OWN trades (R per micro after costs, each counted once it has closed before the
entry), exactly what engine/second.run gives the live bot (the trades of LIT's live window), so the same rule works live;
it is not reset by a new eval (a bad market is a bad market).

Picked on 2025 + 2021-24 (the failure years), checked on 2026 H1 / H2 (must stay within ~10% of today's 2-week pass and
eval-path $). Scored like tools/second_account_b.py: fresh eval every session (2-week / 1-month pass / fail / stuck), pass
within 60 sessions, back-to-back eval path $, $ per eval bought = p60 x funded $ in 3 months (research/second/account_b.json,
the funded account trades the safe size, no brake) - the price; Builder 25K and 50K.

    python -X utf8 tools/second_brake.py            # grid -> research/second/brake.json (+ table); ~3 min
    python -X utf8 tools/second_brake.py save       # + rl.save the base and the best brakes (sb_brake_*)
Paper research only. Needs research/runs/_cache/second_mix_units.pkl (python -X utf8 tools/second_mix.py units).
"""
from __future__ import annotations

import bisect
import collections
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import second_mix as M  # noqa: E402
from tools import second_account_b as AB  # noqa: E402

OUT = os.path.join(ROOT, "research", "second", "brake.json")
NAMES = ("EMA", "MD", "SR")
SPANS = ("H1", "H2", "2025", "2021-24")
PICK, CHECK = ("2025", "2021-24"), ("H1", "H2")
PLANS = ("builder25k", "builder50k")
PV, COMM, SLIP_STOP = 2.0, 1.90, 0.5


# ================================================================================================ brake signals
def r_of(u):
    return (u["pts"] * PV - COMM) / (u["risk"] * PV)


def history():
    """The strategies' own trades (raw, before the no-hedge cut) in exit order: (exit_t, r, week key)."""
    u = M.units()
    H = sorted(((int(t["exit_t"]), r_of(t), t["day"]) for nm in NAMES for t in u[nm]), key=lambda x: x[0])
    return H


def _week(day):
    y, w, _ = dt.date.fromisoformat(day).isocalendar()
    return (y, w)


_VOL = {}


def prior_close(name, day):
    """The CBOE close of the last date before `day` (known before the session)."""
    if name not in _VOL:
        v = pd.read_csv(os.path.join(ROOT, "data", f"{name}_1d.csv"))
        v = v[v["close"] > 0]
        _VOL[name] = (list(v["date"].astype(str)), v["close"].values.astype(float))
    d, c = _VOL[name]
    j = bisect.bisect_left(d, day) - 1
    return float(c[j]) if j >= 0 else None


def brake_mult(spec, t, H, HT):
    """The brake's size multiplier for trade t (1 = full, 0.5 = half, 0 = no trade) from history only."""
    if spec is None or spec.get("kind") == "fit":
        return 1.0
    k = spec["kind"]
    i = bisect.bisect_right(HT, int(t["entry_t"]))          # trades closed at or before this entry
    past = H[:i]
    if k == "streak":
        n = 0
        for _, r, _ in reversed(past):
            if r < 0:
                n += 1
            else:
                break
        return spec.get("mult", 0.5) if n >= spec["n"] else 1.0
    if k == "sum":
        last = [r for _, r, _ in past[-spec["k"]:]]
        if len(last) < spec["k"]:
            return 1.0
        return spec.get("mult", 0.5) if sum(last) <= 0 else 1.0
    if k == "week":
        wk = _week(t["day"])
        s = sum(r for _, r, d in past if _week(d) == wk)
        return spec.get("mult", 0.0) if s <= -spec["x"] else 1.0
    if k in ("vxn", "vix"):
        v = prior_close(k.upper(), t["day"])
        if v is None:
            return 1.0
        return 1.0 if spec["lo"] <= v < spec["hi"] else spec.get("mult", 0.5)
    raise ValueError(k)


def grid():
    G = {"base": None, "fit": {"kind": "fit"}}
    for n in (2, 3, 4, 5):
        G[f"streak{n}"] = {"kind": "streak", "n": n}
    for k in (5, 8, 10, 15, 20):
        G[f"sum{k}"] = {"kind": "sum", "k": k}
        G[f"sum{k}_q"] = {"kind": "sum", "k": k, "mult": 0.25}
        G[f"sum{k}_skip"] = {"kind": "sum", "k": k, "mult": 0.0}
    for x in (2.0, 3.0, 4.0):
        G[f"wk{x:g}"] = {"kind": "week", "x": x}
        G[f"wk{x:g}_half"] = {"kind": "week", "x": x, "mult": 0.5}
    for nm in ("vxn", "vix"):
        los = (0, 15, 18, 20) if nm == "vix" else (0, 18, 20, 22)
        his = (25, 30, 35, 99) if nm == "vix" else (28, 32, 36, 99)
        for lo in los:
            for hi in his:
                if lo == 0 and hi == 99:
                    continue
                G[f"{nm}{lo}-{hi}"] = {"kind": nm, "lo": lo, "hi": hi}
    return G


# ================================================================================================ executor (+ brake)
def play_day(L, day, bal, floor, session, rule, mults, fit=False):
    """tools/second_mix.play_day for account B (reserve off, max 2 a day, M.DLL) with the brake's multiplier per trade."""
    cum, busy, n, recs = 0.0, 0, 0, []
    dll = M.DLL
    for t in L:
        if cum <= -dll:
            break
        if t["entry_t"] < busy or n >= 2:
            continue
        room = bal + cum - floor
        if fit and (t["risk"] + SLIP_STOP) * PV + COMM >= room:
            continue
        st = {"profit": bal, "cum": cum, "room": room, "session": session, "n_today": 0}
        q = M.second_q(t, st, rule)
        if q <= 0:
            continue
        m = mults.get((t["src"], t["entry_t"]), 1.0)
        if m <= 0:
            continue
        if m < 1.0:
            q = max(1, int(q * m + 1e-9))
        pts, w1, ex, xt = t["pts"], t["w1"], t["exit"], t["exit_t"]
        pnl = pts * PV * q - M.ECOMM * q
        low = min(0.0, w1 * PV * q - M.ECOMM * q, pnl)
        if cum + low <= -dll:
            pnl = -dll - cum - M.SLIP * PV * q
            low = pnl
        recs.append({"day": day, "entry_t": t["entry_t"], "exit_t": xt, "dir": t["dir"], "exit": ex, "risk": t["risk"],
                     "tgt": t["tgt"], "src": t["src"], "qty": q, "pnl": round(pnl, 2), "low": round(low, 2),
                     "risk_usd": round(t["risk"] * PV * q, 2), "mult": m})
        busy = xt; n += 1
        if bal + cum + low <= floor:
            return cum, recs, True
        cum += pnl
    return cum, recs, False


def run_eval(days, by, rule, mults, horizon=20, keep=None, fit=False):
    """tools/second_account_b.run_eval with the brake."""
    bal = peak = 0.0
    floor = -M.MLL
    for kk, day in enumerate(days[:horizon]):
        cum, recs, failed = play_day(by.get(day, ()), day, bal, floor, kk + 1, rule, mults, fit)
        if keep is not None:
            keep.extend(recs)
        if failed:
            return "FAIL", kk + 1
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - M.MLL), M.LOCK)
        if bal >= M.TGT:
            return "PASS", kk + 1
        if not fit and bal - floor < AB.MIN_ROOM:
            return "STUCK", kk + 1
        if fit and bal - floor < (6.0 + SLIP_STOP) * PV + COMM:       # not even a 6-pt stop fits: dead for good
            return "STUCK", kk + 1
    return "OPEN", min(len(days), horizon)


def score(U, mults, plan, fit=False, spans=SPANS, fund=None):
    by = M.by_day(U)
    allS = M.units()["sessions"]
    rule = "acctb_need"
    out = {}
    paths = {}
    for span in spans:
        a, z = M.SPANS[span]
        ix = [i for i, d in enumerate(allS) if a <= d <= z]
        S = [allS[i] for i in ix]
        res = [(run_eval(S[i:i + 20], by, rule, mults, fit=fit), len(S) - i) for i in range(len(S))]
        o = {"starts": len(S)}
        for lab, h in (("10", 10), ("20", 20)):
            R = [r for r, av in res if av >= h]
            N = len(R) or 1
            o["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
            o["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
            o["s" + lab] = round(100.0 * sum(1 for r in R if r[0] == "STUCK" and r[1] <= h) / N, 1)
            o["dead" + lab] = round(o["f" + lab] + o["s" + lab], 1)
        pas = [r[1] for r, _ in res if r[0] == "PASS" and r[1] <= 20]
        o["pass_med"] = float(np.median(pas)) if pas else None
        E = [run_eval(allS[i:i + 60], by, rule, mults, 60, fit=fit) for i in ix if i + 60 <= len(allS)]
        o["p60"] = round(100.0 * sum(1 for r in E if r[0] == "PASS") / len(E), 1) if E else None
        f3 = (fund or {}).get(span)
        o["ev_eval"] = round(o["p60"] / 100.0 * f3 - M.PRICE) if (o["p60"] is not None and f3 is not None) else None
        k, T, n = 0, [], collections.Counter()
        while k < len(S):
            r, used = run_eval(S[k:], by, rule, mults, len(S) - k, keep=T, fit=fit)
            n[r] += 1
            if r == "OPEN":
                break
            k += used
        p = np.array([t["pnl"] for t in T]) if T else np.zeros(1)
        gl = -p[p < 0].sum()
        eq = np.cumsum(p)
        nb = n["PASS"] + n["FAIL"] + n["STUCK"] + (1 if n["OPEN"] else 0)
        o.update(n=len(T), tpw=round(len(T) / (len(S) / 5), 2), net=round(float(p.sum())), pf=round(float(p[p > 0].sum() / gl), 2) if gl else None,
                 dd=round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())), evals=nb, passes=n["PASS"],
                 net_less_fees=round(float(p.sum()) - nb * M.PRICE), braked=sum(1 for t in T if t.get("mult", 1.0) < 1.0))
        # real money of the back-to-back path: eval profit is never paid out; each pass becomes a funded account worth
        # f3 (3 months of payouts, research/second/account_b.json), each eval bought costs the price
        o["cash"] = round(n["PASS"] * f3 - nb * M.PRICE) if f3 is not None else None
        out[span] = o
        paths[span] = T
    return out, paths


def fund_3m(plan):
    d = json.load(open(os.path.join(ROOT, "research", "second", "account_b.json"), encoding="utf-8"))
    return {s: d["plans"][f"{plan}|need"][s]["fund_paid_3m"] for s in SPANS}


def mults_for(spec, U, H, HT):
    return {(t["src"], t["entry_t"]): brake_mult(spec, t, H, HT) for t in U}


def verdict_row(o, b):
    """Pick-years gain and the 2026 cost vs base (same plan)."""
    pick_dead = np.mean([o[s]["dead10"] for s in PICK]) - np.mean([b[s]["dead10"] for s in PICK])
    pick_p10 = np.mean([o[s]["p10"] for s in PICK]) - np.mean([b[s]["p10"] for s in PICK])
    pick_ev = sum(o[s]["ev_eval"] or 0 for s in PICK) - sum(b[s]["ev_eval"] or 0 for s in PICK)
    pick_net = sum(o[s]["net_less_fees"] for s in PICK) - sum(b[s]["net_less_fees"] for s in PICK)
    pick_cash = sum(o[s]["cash"] or 0 for s in PICK) - sum(b[s]["cash"] or 0 for s in PICK)
    chk_cash = sum(o[s]["cash"] or 0 for s in CHECK) - sum(b[s]["cash"] or 0 for s in CHECK)
    chk_p10 = min((o[s]["p10"] / b[s]["p10"]) if b[s]["p10"] else 1.0 for s in CHECK)
    chk_net = min((o[s]["net"] / b[s]["net"]) if b[s]["net"] > 0 else 1.0 for s in CHECK)
    return {"pick_dead10": round(float(pick_dead), 1), "pick_p10": round(float(pick_p10), 1), "pick_ev": round(float(pick_ev)),
            "pick_net_less_fees": round(float(pick_net)), "pick_cash": round(float(pick_cash)), "check_cash": round(float(chk_cash)),
            "check_p10_kept": round(100 * chk_p10, 1), "check_net_kept": round(100 * chk_net, 1)}


def main(save=False):
    M.units()
    U = M.acct_units(NAMES, nohedge=True)
    H = history()
    HT = [h[0] for h in H]
    G = grid()
    out = {"grid": {}, "notes": __doc__.split("\n\n")[1]}
    paths = {}
    for plan in PLANS:
        fund = fund_3m(plan)
        with AB.Plan(plan):
            res = {}
            for nm, spec in G.items():
                mm = mults_for(spec, U, H, HT)
                o, P = score(U, mm, plan, fit=bool(spec and spec.get("kind") == "fit"), fund=fund)
                res[nm] = o
                paths[(plan, nm)] = P
            b = res["base"]
            for nm, o in res.items():
                out["grid"][f"{plan}|{nm}"] = {"spec": G[nm], "spans": o, "vs_base": verdict_row(o, b)}
    # rank on the pick years (25K = the account B pick): dead10 down, $ per eval up, with 2026 kept >= 90%
    rows = []
    for key, x in out["grid"].items():
        plan, nm = key.split("|")
        if nm == "base":
            continue
        v = x["vs_base"]
        ok = v["check_p10_kept"] >= 90.0 and v["check_net_kept"] >= 90.0
        rows.append((plan, nm, ok, v))
    out["ranked"] = {}
    for plan in PLANS:
        R = sorted([r for r in rows if r[0] == plan], key=lambda r: (not r[2], -r[3]["pick_cash"], -r[3]["pick_dead10"]))
        out["ranked"][plan] = [{"brake": nm, "keeps_2026": ok, **v} for _, nm, ok, v in R]
    json.dump(out, open(OUT, "w"), indent=1, default=float)
    show(out)
    if save:
        store(out, paths)
    return out


def line(o):
    return " | ".join(f"{s} 2w {o[s]['p10']}/{o[s]['dead10']} 1m {o[s]['p20']}/{o[s]['dead20']} p60 {o[s]['p60']} "
                      f"ev {o[s]['ev_eval']} path {o[s]['net']:+,}" for s in SPANS)


def show(out, top=12):
    for plan in PLANS:
        print(f"\n{plan} base: {line(out['grid'][plan + '|base']['spans'])}")
        for r in out["ranked"][plan][:top]:
            o = out["grid"][f"{plan}|{r['brake']}"]["spans"]
            print(f"  {r['brake']:12s} keep26={r['keeps_2026']!s:5s} pick dead {r['pick_dead10']:+.1f} p10 {r['pick_p10']:+.1f} ev {r['pick_ev']:+} "
                  f"net-fees {r['pick_net_less_fees']:+,} cash {r['pick_cash']:+,} (2026 {r['check_cash']:+,}) | 2026 p10 kept {r['check_p10_kept']}% net kept {r['check_net_kept']}%")
            print("       " + line(o))


def store(out, paths, picks=None):
    from tools import runlib as rl
    sess = [d for d in M.units()["sessions"] if d >= "2021-01-01"]
    Q = "Owner 2026-10-22: a bad-market brake for account B (2021-25 evals die within 2 weeks)"
    picks = picks or list(dict.fromkeys(["base"] + [r["brake"] for r in out["ranked"]["builder25k"][:2]] + ["vxn20-99", "sum8_q"]))
    for nm in picks:
        key = f"builder25k|{nm}"
        P = []
        for s in SPANS:
            P += paths[("builder25k", nm)][s]
        T = [{"day": x["day"], "entry_t": x["entry_t"], "exit_t": x["exit_t"], "dir": x["dir"],
              "r": round(x["pnl"] / x["risk_usd"], 3) if x["risk_usd"] else 0.0, "pnl": x["pnl"], "risk_pts": x["risk"], "qty": x["qty"],
              "risk_usd": x["risk_usd"], "half": False, "exit": x["exit"], "trigger": x["src"], "mfe": None, "mae": None,
              "bars_held": None, "regime": "", "mult": x.get("mult"), "low": x["low"]} for x in P]
        o = out["grid"][key]["spans"]
        rl.save(f"sb_brake_{nm.replace('-', '_').replace('.', '_')}", f"Account B brake: {nm} (Builder 25K)", "risk", Q,
                params={"brake": out["grid"][key]["spec"], "plan": "builder25k", "size": "need", "no_hedge": True},
                sizing={"plan": "builder25k", "brake": nm}, trades=T, scored=rl.score(T, sess),
                status="info", verdict=line(o), writeup="second-prelaunch", tags=["second", "account_b", "brake"],
                notes="tools/second_brake.py; stored trades = the back-to-back eval path of each span.")
        print("saved", nm)


if __name__ == "__main__":
    main(save=len(sys.argv) > 1 and sys.argv[1] == "save")
