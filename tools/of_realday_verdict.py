"""REAL-DATA VERDICT for order flow (big-ofreal 2026-11-26). One command, run after the PC's order-flow summaries are pulled
(`python tools/data_pull.py --latest --of` -> data/pc_days/<day>/of/). Research only, paper: it changes no bot, size or setting.

On every real recorded tick day it finds (>= 50,000 trades, of_battery.MIN_ROWS):
  1. the pre-registered battery (research/orderflow/DESIGN.md, OF1-OF6; its own looks 40 / 60 / 120 / 250 days),
  2. the Order Flow pillar's paper bot (engine/of_paper.py, DESIGN_paper.md) replayed on each day's 5m summary:
     lane A (absorbed level fade: TAKEN vs SKIPPED, R and $), lane B (OF1 at Zlarior's sweep: the LIT replay's trades AND the
     real ledger trades the PC sent, in $), lane C (needs raw depth snapshots: PC-side only, listed),
  3. scores them against the bars written BEFORE the data (DESIGN_paper.md "Scoring"):
     lane A: >= 40 resolved candidates; TAKEN mean R > SKIPPED mean R with a one-sided label-shuffle p < 0.10, the same sign in
             the older and newer half of the days, and TAKEN mean $ (1 micro, costs in) > 0.
     lane B: >= 20 LIT trades; the "take" trades' $ > all trades' $, skip-placebo p < 0.10 (as the battery's OF1).
  -> research/orderflow/real_verdict.json + research/orderflow/real_verdict.md (one page, plain words).
Honest labels: "TOO FEW" under the floors; "history days, tick-rule sides" when NinjaTrader's history quotes were filled in;
days before 2026-11-27 are HISTORY (the rules were frozen before they were seen, but they are not forward days).

    python -X utf8 tools/of_realday_verdict.py                 # the pulled real days (data/pc_days + logs/datapipe/days)
    python -X utf8 tools/of_realday_verdict.py --src DIR       # another days folder
    python -X utf8 tools/of_realday_verdict.py --sim [--null]  # the pipeline on simulated days (written to a temp folder)
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import importlib.util
import json
import os
import sys
import tempfile
import zlib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT_J = os.path.join(ROOT, "research", "orderflow", "real_verdict.json")
OUT_MD = os.path.join(ROOT, "research", "orderflow", "real_verdict.md")
FORWARD_FROM = "2026-11-27"                      # DESIGN_paper.md was frozen 2026-11-26: later days are forward days
MIN_A, MIN_B, N_PERM, P_BAR = 40, 20, 2000, 0.10


def _of_mod(name):
    sp = importlib.util.spec_from_file_location(f"orv_{name}", os.path.join(ROOT, "research", "orderflow", name + ".py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


# ------------------------------------------------------------------------------------------------ inputs
def ledger_lit(day_dir: str) -> list:
    """Zlarior's real entries of one pulled day (trades.jsonl.gz from engine/datapipe): [{"t", "d", "stop", "pnl"}]."""
    p = os.path.join(day_dir, "trades.jsonl.gz")
    rows = []
    try:
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            rows = [json.loads(x) for x in fh if x.strip()]
    except (OSError, ValueError):
        return []
    ent, pnl = {}, {}
    for r in rows:
        if r.get("bot") not in (None, "zlarior") or str(r.get("src") or "main") != "main" or str(r.get("mode") or "") == "paper":
            continue
        try:
            et_ = int(r.get("entry_t") or 0)
        except (TypeError, ValueError):
            continue
        if not et_:
            continue
        if r.get("side") in ("buy", "sell") and r.get("stop"):
            ent.setdefault(et_, {"t": et_, "d": 1 if r["side"] == "buy" else -1, "stop": float(r["stop"])})
        elif r.get("side") == "exit" and r.get("pnl") is not None:
            pnl.setdefault(et_, {})[int(r.get("t") or 0)] = float(r["pnl"])
    return [{**e, "pnl": round(sum(pnl[k].values()), 2) if k in pnl else None} for k, e in sorted(ent.items())]


def day_dirs(src=None) -> dict:
    out = {}
    for base in ([src] if src else [os.path.join(ROOT, "data", "pc_days"), os.path.join(ROOT, "logs", "datapipe", "days")]):
        if base and os.path.isdir(base):
            for d in sorted(os.listdir(base)):
                if len(d) == 10 and os.path.exists(os.path.join(base, d, "of", "NQ_meta.json")):
                    out.setdefault(d, os.path.join(base, d))
    return out


# ------------------------------------------------------------------------------------------------ scoring
def perm_p(x, lab, seed, n=N_PERM):
    """One-sided: P(mean x[lab] - mean x[~lab] >= observed) under shuffled labels."""
    x = np.asarray(x, float); lab = np.asarray(lab, bool)
    if lab.sum() == 0 or (~lab).sum() == 0:
        return None
    obs = x[lab].mean() - x[~lab].mean()
    rng = np.random.default_rng(seed)
    k = int(lab.sum())
    hits = sum(1 for _ in range(n) if (lambda m: x[m].mean() - x[~m].mean())(np.isin(np.arange(len(x)), rng.choice(len(x), k, replace=False))) >= obs - 1e-12)
    return round((hits + 1) / (n + 1), 4)


def stats(R, usd):
    R = np.asarray(R, float); usd = np.asarray(usd, float)
    if not len(R):
        return {"n": 0}
    return {"n": int(len(R)), "mean_R": round(float(R.mean()), 3), "sum_R": round(float(R.sum()), 2), "win%": round(100 * float((R > 0).mean()), 1),
            "usd_1": round(float(usd.sum()), 2), "usd_1_mean": round(float(usd.mean()), 2)}


def score_a(rows, days):
    res = [r for r in rows if r.get("R") is not None]
    out = {"candidates": len(rows), "resolved": len(res), "need": MIN_A}
    tk = np.array([r["taken"] for r in res], bool)
    R = np.array([r["R"] for r in res], float); U = np.array([r["usd_1"] for r in res], float)
    out["taken"], out["skipped"] = stats(R[tk], U[tk]), stats(R[~tk], U[~tk])
    ab = np.array([bool(r["absorbed"]) for r in res], bool)
    out["info_absorbed_vs_not"] = {"absorbed": stats(R[ab], U[ab]), "not_absorbed": stats(R[~ab], U[~ab])}
    out["p"] = perm_p(R, tk, zlib.crc32(b"laneA")) if len(res) else None
    half = sorted(days)[(len(days) + 1) // 2 - 1] if days else None
    hv = []
    for m in (np.array([r["day"] <= half for r in res], bool), np.array([r["day"] > half for r in res], bool)):
        a, b = R[tk & m], R[~tk & m]
        hv.append(round(float(a.mean() - b.mean()), 3) if len(a) and len(b) else None)
    out["halves_diff_R"] = hv
    if len(res) < MIN_A or tk.sum() == 0 or (~tk).sum() == 0:
        out["verdict"] = f"TOO FEW: {len(res)} of {MIN_A} resolved level signals"
    else:
        ok = (out["taken"]["mean_R"] > out["skipped"]["mean_R"] and (out["p"] or 1) < P_BAR and all(h is not None and h > 0 for h in hv)
              and out["taken"]["usd_1_mean"] > 0)
        out["verdict"] = "YES: absorption separated winners from losers (a candidate: forward days decide)" if ok else "NO: absorption did not separate winners from losers"
    return out


def score_b(recs, label):
    rr = [r for r in recs if r.get("pnl") is not None and r.get("absorbed") is not None]
    out = {"source": label, "trades": len(rr), "need": MIN_B}
    if not rr:
        out["verdict"] = f"TOO FEW: 0 of {MIN_B} LIT trades with an OF read"
        return out
    p = np.array([r["pnl"] for r in rr], float); k = np.array([r["absorbed"] for r in rr], bool)
    out.update({"all_usd": round(float(p.sum())), "take_usd": round(float(p[k].sum())), "gain_usd": round(float(p[k].sum() - p.sum())),
                "kept": int(k.sum()), "won_take": int((p[k] > 0).sum()), "won_skip": int((p[~k] > 0).sum()), "n_skip": int((~k).sum())})
    ns = int((~k).sum())
    if ns:
        rng = np.random.default_rng(zlib.crc32(label.encode()))
        obs = -p[~k].sum()
        ge = sum(-p[rng.choice(len(p), ns, replace=False)].sum() >= obs for _ in range(N_PERM))
        out["skip_placebo_p"] = round((ge + 1) / (N_PERM + 1), 4)
    if len(rr) < MIN_B:
        out["verdict"] = f"TOO FEW: {len(rr)} of {MIN_B} LIT trades"
    else:
        ok = out["gain_usd"] > 0 and (out.get("skip_placebo_p") or 1) < P_BAR
        out["verdict"] = ("YES: OF1 would have improved LIT in $ (a candidate: forward days + the owner decide)" if ok
                          else "NO: OF1 would not have improved LIT in $")
    return out


# ------------------------------------------------------------------------------------------------ run
def run(R=None, lit=None, src=None, ledgers=None, out_json=OUT_J, out_md=OUT_MD, write=True, label="real", say=print) -> dict:
    from engine import of_paper as P
    B = _of_mod("of_battery")
    dirs = {} if R is not None else day_dirs(src)
    if R is None:
        from engine import ofsum
        R = {d: ofsum.read(p) for d, p in dirs.items()}
        R = {d: x for d, x in R.items() if x}
    days = sorted(d for d, x in R.items() if int(x["meta"].get("rows", 0)) >= B.MIN_ROWS)
    out = {"made": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "label": label,
           "design": ["research/orderflow/DESIGN.md", "research/orderflow/DESIGN_paper.md"], "tick_days": len(days),
           "first": days[0] if days else None, "last": days[-1] if days else None,
           "forward_days": sum(1 for d in days if d >= FORWARD_FROM), "dropped_thin": sorted(set(R) - set(days))}
    if not days:
        out["verdict_line"] = "No real order-flow day pulled yet: run tools/of_send_now.py on the PC, then python tools/data_pull.py --latest --of"
        say(out["verdict_line"])
        if write:
            _write(out, out_json, out_md)
        return out
    D = {d: B.Day(d, R[d]) for d in days}
    sq, fwd_q = B.quality(D, days)
    out["sides"] = sq
    qr = [float((R[d]["meta"].get("sides") or {}).get("quote_rule") or 0) for d in days]
    out["side_note"] = ("quote-rule sides (real bid/ask at each trade)" if np.median(qr) >= 0.5 else
                        "tick-rule sides on most days (NinjaTrader history quotes are filled in): delta is an estimate")
    # lane B inputs
    if lit is None:
        try:
            lit, bars_to = B.lit_trades()
        except Exception as e:  # noqa: BLE001
            lit, bars_to = [], f"unavailable ({e.__class__.__name__})"
    else:
        bars_to = "given"
    out["lit_bars_to"] = bars_to
    # 1. battery
    with tempfile.TemporaryDirectory() as td:
        try:
            import contextlib, io
            with contextlib.redirect_stdout(io.StringIO()):
                bt = B.run(raw={d: R[d] for d in days}, lit=(lit, bars_to), atlas=None if label == "real" else ([], "n/a"), write=False, out_dir=td)
            out["battery"] = {"state": bt.get("state"), "look": bt.get("look"), "verdicts": bt.get("verdicts"),
                              "OF1": {k: bt.get("OF1 LIT only when absorbed", {}).get(k) for k in ("Discovery", "Confirm", "skip_placebo_p", "verdict")}}
        except Exception as e:  # noqa: BLE001
            out["battery"] = {"error": f"{e.__class__.__name__}: {str(e)[:160]}"}
    # 2. the paper bot on every day's summary
    rows, recs_real = [], []
    for k, d in enumerate(days):
        prev = days[k - 1] if k and (dt.date.fromisoformat(d) - dt.date.fromisoformat(days[k - 1])).days <= 4 else None
        led = (ledgers or {}).get(d) if ledgers is not None else (ledger_lit(dirs[d]) if d in dirs else [])
        S = P.replay_summary(R[d], d, R[prev] if prev else None, prev, lit=led)
        rows += [r for r in S["rows"]]
        recs_real += S["lit"]
    out["laneA"] = score_a(rows, days)
    # lane B from the LIT replay (the battery's OF1 rows) and from the real ledger
    recs_rep = []
    for t in lit or []:
        ed = B.et_day(t["te"])
        if ed in D:
            z = D[ed].zone(t["te"], t["dir"])
            ab = None if z is None or z[0] <= 0 else bool(z[1] * t["dir"] < 0 and abs(z[1]) >= B.ABS_SHARE * z[0])
            recs_rep.append({"absorbed": ab, "pnl": float(t["pnl"]), "day": ed})
    out["laneB_replay"] = score_b(recs_rep, "LIT replay (what the bot would have traded, costs in)")
    out["laneB_real"] = score_b(recs_real, "Zlarior's real ledger trades")
    out["laneC"] = "needs the raw depth snapshots: scored on the PC only (engine/of_paper lane C), not from summaries"
    fw = [r for r in rows if r["day"] >= FORWARD_FROM and r.get("taken") and r.get("R") is not None]
    out["forward"] = {"taken_resolved": len(fw), "need": 20, "sum_R": round(sum(r["R"] for r in fw), 2),
                      "usd_1": round(sum(r["usd_1"] for r in fw), 2)}
    out["rows"] = [{k: r.get(k) for k in ("id", "day", "level", "d", "absorbed", "taken", "why_not", "R", "usd_1", "why")} for r in rows][-400:]
    a, b1, b2 = out["laneA"], out["laneB_replay"], out["laneB_real"]
    of1 = ((out.get("battery") or {}).get("OF1") or {}).get("verdict") or "not run"
    out["of1_decider"] = of1
    out["verdict_line"] = (f"{len(days)} {'real' if label == 'real' else label} tick days ({out['first']} to {out['last']}). Absorption (lane A): {a['verdict']}. "
                           f"OF1 on LIT, the pre-registered battery test (both halves): {of1}; paper lane B (replay): {b1['verdict']}; "
                           f"real Zlarior trades: {b2['verdict']}.")
    say(out["verdict_line"])
    if write:
        _write(out, out_json, out_md)
    return out


def _fmt(s):
    return "-" if not s or not s.get("n") else f"{s['n']} | {s['mean_R']:+.2f}R | {s['win%']:.0f}% | ${s['usd_1']:+,.0f}"


def markdown(o) -> str:
    real = o.get("label") == "real"
    L = [f"# Order flow on {'REAL NQ ticks' if real else 'SIMULATED ticks (' + o.get('label', '') + ', pipeline test)'}: the verdict ({o['made'][:10]})", "",
         "Research only, paper. Rules frozen before the data: research/orderflow/DESIGN.md (battery), DESIGN_paper.md (paper bot).",
         "Built by `python -X utf8 tools/of_realday_verdict.py`.", ""]
    if not o.get("tick_days"):
        return "\n".join(L + [o["verdict_line"], ""])
    a = o["laneA"]
    L += [f"**Days:** {o['tick_days']} {'real' if real else 'simulated'} tick days, {o['first']} to {o['last']} ({o['forward_days']} forward days from {FORWARD_FROM}; "
          f"the rest are history days the rules never saw). Sides: {o['side_note']}.", "",
          "## 1. Does absorption separate winners from losers? (lane A, the pillar's level fade)", "",
          "| | trades | mean R | won | $ at 1 micro |", "|---|---|---|---|---|",
          f"| TAKEN (absorbed) | {_fmt(a['taken'])} |".replace(" | -", " | -"), f"| SKIPPED (not absorbed / busy) | {_fmt(a['skipped'])} |", "",
          f"Shuffle p = {a.get('p')} (bar < {P_BAR}); older / newer half difference in R: {a.get('halves_diff_R')}. "
          f"Bar: >= {MIN_A} resolved signals, taken > skipped, both halves, taken $ > 0 after costs.", "", f"**{a['verdict']}**", ""]
    L += ["## 2. Does OF1 improve LIT?", "", f"**The decider = the battery's pre-registered OF1 (gain in BOTH halves, keeps >= 50%, placebo): "
          f"{o.get('of1_decider')}.** The paper lane B lines below are the same filter over all days pooled (a weaker view).", ""]
    for key, title in (("laneB_replay", "2a. Paper lane B on the LIT replay"), ("laneB_real", "2b. Paper lane B on Zlarior's REAL trades")):
        b = o[key]
        L += [f"## {title}", ""]
        if b.get("trades"):
            L += [f"{b['trades']} trades: all ${b['all_usd']:+,} vs only-absorbed ${b['take_usd']:+,} (gain ${b['gain_usd']:+,}; kept {b['kept']}, "
                  f"won {b['won_take']} of {b['kept']} kept vs {b['won_skip']} of {b['n_skip']} skipped); skip-placebo p = {b.get('skip_placebo_p')}.", ""]
        L += [f"**{b['verdict']}**", ""]
    bt = o.get("battery") or {}
    L += ["## 3. The pre-registered battery (OF1-OF6)", "", f"State: {bt.get('state')}, look {bt.get('look')}.", ""]
    for k, v in (bt.get("verdicts") or {}).items():
        L.append(f"- {k}: {v}")
    L += ["", f"Forward score (lane A taken trades on days from {FORWARD_FROM}): {o['forward']['taken_resolved']} of {o['forward']['need']}, "
          f"{o['forward']['sum_R']:+.1f}R.", "", "Nothing here changes a bot. A YES is a candidate for the forward test and then the owner's decision."]
    return "\n".join(L) + "\n"


def _write(o, pj, pm):
    os.makedirs(os.path.dirname(pj), exist_ok=True)
    with open(pj, "w", encoding="utf-8") as fh:
        json.dump(o, fh, indent=1, default=float)
    with open(pm, "w", encoding="utf-8") as fh:
        fh.write(markdown(o))


def sim(null=False, n=45, out_dir=None, say=print):
    Sim = _of_mod("of_sim")
    W = Sim.world(n, "null" if null else "planted", seed=41, lvl=True)
    led = {}
    for t in W["lit"]:
        led.setdefault(t["day"], []).append({"t": t["tn"], "d": t["dir"], "stop": 0.0, "pnl": t["pnl"]})
    od = out_dir or tempfile.mkdtemp()
    return run(R=W["R"], lit=W["lit"], ledgers=led, out_json=os.path.join(od, "real_verdict.json"), out_md=os.path.join(od, "real_verdict.md"),
               label="sim-null" if null else "sim-planted", say=say)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src"); ap.add_argument("--sim", action="store_true"); ap.add_argument("--null", action="store_true")
    a = ap.parse_args()
    if a.sim:
        o = sim(a.null)
    else:
        run(src=a.src)
