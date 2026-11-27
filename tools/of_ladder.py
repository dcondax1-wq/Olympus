"""Order flow lane A gate ladder, scored every night (night-of-ladder 2026-11-27). PAPER RESEARCH ONLY.

The ladder and its stop rules were set before any forward trade: research/evalplan/PLAN.md section 3. This file only COUNTS:
it never arms, routes, sizes or switches anything. A passed gate writes a Decide card DRAFT (research/evalplan/card_gate.json)
for the lead to wire; the owner's yes is always the next step.

    python -X utf8 tools/of_ladder.py            -> research/evalplan/ladder.json (+ card_gate.json only when a gate passed)

Forward lane A trades (from 2026-11-27): the PC paper bot's shipped days (data/pc_days/<day>/of/NQ_paper.json.gz) first,
else the cloud replay rows in research/orderflow/real_verdict.json. A row's fill-at-E5 R (R_e5, or fill_e5 vs fill when
the PC logs it) is reported beside the original fill; the gates judge the WORSE of the two.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "evalplan", "ladder.json")
CARD = os.path.join(ROOT, "research", "evalplan", "card_gate.json")
VERDICT = os.path.join(ROOT, "research", "orderflow", "real_verdict.json")
PC_DAYS = os.path.join(ROOT, "data", "pc_days")
SIM_ROWS = os.path.join(ROOT, "data", "of_ladder_sim.json")     # step 1+ rows, once the lead builds the Sim101 route (absent = none)
FWD_FROM = "2026-11-27"
PLAN = "research/evalplan/PLAN.md"

# the ladder exactly as PLAN.md section 3 (do not loosen after seeing forward data)
STEPS = [
    {"step": 0, "name": "paper forward", "where": "the paper bot (scored nightly)",
     "gate": "20 forward trades with >= 9 won (mean >= +0.35R, $ > 0 at 1 micro)",
     "stop": "after 10 forward trades <= 2 won, or the forward sum <= -6R at any time"},
    {"step": 1, "name": "Sim101", "where": "NinjaTrader Sim101, same rules, real order path",
     "gate": "10 Sim101 trades, fills within 2 ticks of paper on average, 0 hedge / one-position conflicts",
     "stop": "any hedge conflict, or fills worse than paper by > 4 ticks on average"},
    {"step": 2, "name": "one eval", "where": "Zlarior 25K #2, $100 a trade, quiet days only, 1 a day / 3 a week (owner yes + phrase)",
     "gate": "pooled forward 40 trades with >= 17 won (+0.28R)",
     "stop": "lane A's own sum on the account <= -$300, or 10 eval trades <= 2 won, or the account's room under $400"},
    {"step": 3, "name": "the other evals", "where": "Zlarior 50K at $200, Rapid EOD 25K at $100 with the news window",
     "gate": "60 forward trades, mean >= +0.25R in both halves of the forward",
     "stop": "lane A's sum <= -$300 (25K) / -$600 (50K) on an account"},
    {"step": 4, "name": "ATLAS funded", "where": "ATLAS Builder 25K funded, $100, after its first $1,000 payout",
     "gate": "2 months of step 3 with lane A $ > 0 on every account", "stop": "lane A's sum <= -$250 on the funded account = off for good"},
]
G0_N, G0_WON, S0_FIRST, S0_FIRST_WON, S0_SUM = 20, 9, 10, 2, -6.0
G1_N, G1_GAP, S1_GAP = 10, 2.0, 4.0
G2_N, G2_WON = 40, 17
RATE = 40 / 43                                   # lane A trades a session on the 43 real tick days (research/evalplan/PLAN.md)


def _read(p, default=None):
    try:
        if p.endswith(".gz"):
            with gzip.open(p, "rt", encoding="utf-8") as fh:
                return json.load(fh)
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def r_e5(r):
    """The fill-at-E5 R when the PC logged it: R_e5 as given, else R moved by (fill_e5 - fill) in stop units."""
    if r.get("R_e5") is not None:
        return float(r["R_e5"])
    f, f5, st, d = r.get("fill"), r.get("fill_e5"), r.get("stop"), r.get("d")
    if None in (f, f5, st, d) or r.get("R") is None:
        return None
    risk = abs(float(f) - float(st))
    if risk <= 0:
        return None
    return float(r["R"]) - float(d) * (float(f5) - float(f)) / risk


def _done(r):
    return bool(r.get("taken")) and r.get("R") is not None and str(r.get("day") or "") >= FWD_FROM


def forward_rows(pc_days=None, verdict=None):
    """(rows, source): the forward taken + resolved lane A trades, one list, oldest first, no duplicates (by id)."""
    pc_days, verdict = pc_days or PC_DAYS, verdict or VERDICT
    seen, out, src = set(), [], []
    if os.path.isdir(pc_days):
        for d in sorted(os.listdir(pc_days)):
            S = _read(os.path.join(pc_days, d, "of", "NQ_paper.json.gz"))
            if not isinstance(S, dict):
                continue
            n0 = len(out)
            for r in S.get("rows") or []:
                if isinstance(r, dict) and _done(r) and (r.get("id") or (r.get("day"), r.get("level"))) not in seen:
                    seen.add(r.get("id") or (r.get("day"), r.get("level")))
                    out.append(dict(r, src="pc"))
            if len(out) > n0 and "PC paper bot" not in src:
                src.append("PC paper bot")
    V = _read(verdict, {}) or {}
    n0 = len(out)
    pc_days_seen = {r["day"] for r in out}
    for r in V.get("rows") or []:
        if isinstance(r, dict) and _done(r) and r["day"] not in pc_days_seen and (r.get("id") or (r.get("day"), r.get("level"))) not in seen:
            seen.add(r.get("id") or (r.get("day"), r.get("level")))
            out.append(dict(r, src="replay"))
    if len(out) > n0:
        src.append("cloud replay (real_verdict.json)")
    out.sort(key=lambda r: (r["day"], r.get("t") or 0))
    return out, src


def _stats(rows):
    R = [float(r["R"]) for r in rows]
    R5 = [r_e5(r) for r in rows]
    have5 = [x for x in R5 if x is not None]
    judged = [min(a, b) if b is not None else a for a, b in zip(R, R5)]
    won = sum(1 for x in judged if x > 0)
    gw, gl = sum(x for x in judged if x > 0), -sum(x for x in judged if x < 0)
    return {"n": len(rows), "won": won, "sum_R": round(sum(judged), 2), "mean_R": round(sum(judged) / len(judged), 3) if judged else None,
            "pf": round(gw / gl, 2) if gl > 0 else None, "usd_1": round(sum(float(r.get("usd_1") or 0) for r in rows), 2),
            "orig_sum_R": round(sum(R), 2), "e5_n": len(have5), "e5_sum_R": round(sum(have5), 2) if have5 else None}


def gate0(rows):
    """-> ("stopped" | "passed" | "watching", why)"""
    st = _stats(rows)
    first = _stats(rows[:S0_FIRST])
    if st["n"] and st["sum_R"] <= S0_SUM:
        return "stopped", f"forward sum {st['sum_R']}R <= {S0_SUM}R"
    if len(rows) >= S0_FIRST and first["won"] <= S0_FIRST_WON:
        return "stopped", f"first {S0_FIRST} forward trades won only {first['won']}"
    if st["n"] >= G0_N:                     # judged ONCE, on the first 20 forward trades (no re-tries after a miss)
        g = _stats(rows[:G0_N])
        if g["won"] >= G0_WON and g["usd_1"] > 0:
            return "passed", f"first {G0_N} forward trades: {g['won']} won, {g['sum_R']:+.1f}R, ${g['usd_1']:,.0f} at 1 micro"
        return "stopped", f"first {G0_N} forward trades won {g['won']} (needs {G0_WON}) / ${g['usd_1']:,.0f} at 1 micro: gate 0 missed"
    return "watching", f"{st['n']} / {G0_N} forward trades, {st['won']} won (needs {G0_WON})"


def gate1(sim):
    if not sim:
        return "waiting", "no Sim101 lane A trades yet (the Sim101 route is not built; the lead builds it after gate 0)"
    if any(r.get("hedge_conflict") or r.get("one_position_conflict") for r in sim):
        return "stopped", "a hedge / one-position conflict on Sim101"
    gaps = [float(r["fill_gap_ticks"]) for r in sim if r.get("fill_gap_ticks") is not None]
    avg = sum(gaps) / len(gaps) if gaps else None
    if avg is not None and len(gaps) >= 3 and avg > S1_GAP:
        return "stopped", f"Sim101 fills {avg:.1f} ticks worse than paper on average (> {S1_GAP})"
    if len(sim) >= G1_N and avg is not None and avg <= G1_GAP:
        return "passed", f"{len(sim)} Sim101 trades, fills {avg:.1f} ticks from paper, 0 conflicts"
    return "watching", f"{len(sim)} / {G1_N} Sim101 trades" + (f", fills {avg:.1f} ticks from paper" if avg is not None else "")


def evaluate(rows, sim=None, prev=None, today=None):
    """The ladder state. A stop is sticky (prev['stopped'] stays). Steps >= 2 need the owner's yes: the ladder only says 'ask'."""
    prev = prev or {}
    st = _stats(rows)
    g0, why0 = gate0(rows)
    step, status, why, passed, gwhy = 0, g0, why0, -1, None   # passed = the highest gate passed; step = the one being scored now
    if g0 == "passed":
        passed, gwhy = 0, why0
        g1, why1 = gate1(sim or [])
        step, status, why = 1, g1, why1
        if g1 == "passed":
            passed, gwhy = 1, why1
            pooled = _stats(rows + list(sim or []))
            step, status = 2, "ask_owner"
            why = (f"Sim101 passed; step 2 (one eval) needs your yes. Its own gate later: pooled {pooled['n']} / {G2_N} trades, "
                   f"{pooled['won']} won (needs {G2_WON})")
    if prev.get("stopped"):
        step, status, why = prev["stopped"]["step"], "stopped", prev["stopped"]["why"] + " (stopped earlier: stays paper)"
    stopped = prev.get("stopped") or ({"step": step, "why": why, "on": today} if status == "stopped" else None)
    nxt = STEPS[min(step + 1, len(STEPS) - 1)]
    card_due = passed >= 0 and not stopped
    return {"v": 1, "paper_only": True, "plan": PLAN, "fwd_from": FWD_FROM, "step": step, "step_name": STEPS[step]["name"],
            "status": status, "why": why, "stats": st, "gate": STEPS[step]["gate"], "stop_rule": STEPS[step]["stop"],
            "next": {"step": nxt["step"], "name": nxt["name"], "gate": nxt["gate"], "stop": nxt["stop"]},
            "stopped": stopped, "card_due": card_due, "passed_gate": passed, "passed_why": gwhy, "steps": STEPS,
            "line": line(step, status, st, why)}


def line(step, status, st, why):
    head = {"watching": "watching", "passed": "GATE PASSED", "ask_owner": "GATE PASSED - your yes needed", "stopped": "STOPPED",
            "waiting": "waiting"}.get(status, status)
    return (f"Order flow ladder step {step} ({STEPS[step]['name']}): {head}. {why}."
            f" Forward so far: {st['n']} trades, {st['won']} won, {st['sum_R']:+.1f}R (1 micro ${st['usd_1']:+,.0f}).")


def card(doc):
    """The Decide card draft for the highest passed gate (the lead wires it into tools/web_public/business/decisions.json)."""
    s, g = doc["stats"], doc["passed_gate"]
    nx = STEPS[g + 1]
    money = nx["step"] >= 2
    return {"id": f"of-ladder-step{nx['step']}",
            "question": f"Order flow passed step {g} ({STEPS[g]['name']}): start step {nx['step']} ({nx['name']})?",
            "why": f"{s['n']} forward trades since {FWD_FROM}: {s['won']} won, {s['sum_R']:+.1f}R, ${s['usd_1']:,.0f} at 1 micro. "
                   f"Gate passed: {doc['passed_why']}.",
            "impact": f"Step {nx['step']}: {nx['where']}. Its gate: {nx['gate']}. Its stop rule: {nx['stop']}.",
            "impact_usd": 0, "options": ["yes", "no", "later"], "status": "open", "source": "research/evalplan/ladder.json + " + PLAN,
            "applies": ("A yes lets the lead switch lane A on for that account only (default OFF; you type the live phrase yourself)."
                        if money else "No real money: a yes lets the lead build the NinjaTrader Sim101 route for lane A (switch default OFF)."),
            "added": dt.date.today().isoformat(), "usd_month": 0,
            "risk": "the next step's stop rule switches it off by itself" + (" (at most about $300 on the eval)" if money else " (Sim101 = no money)"),
            "recommend": "later" if money else "yes",
            "recommend_why": ("Real money is your call; the gate passed but the edge may still be smaller than measured."
                              if money else "The pre-set gate passed on new days and Sim101 costs nothing."), "answered": None}


def run(out=None, card_path=None, say=print, today=None):
    out, card_path = out or OUT, card_path or CARD
    rows, src = forward_rows()
    sim = _read(SIM_ROWS, []) or []
    prev = _read(out, {}) or {}
    doc = evaluate(rows, sim if isinstance(sim, list) else [], prev, today or dt.date.today().isoformat())
    doc["sources"] = src
    doc["built"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    doc["rows"] = [{k: r.get(k) for k in ("id", "day", "level", "d", "R", "usd_1", "src")} | {"R_e5": r_e5(r)} for r in rows][-60:]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    if doc["card_due"]:
        with open(card_path, "w", encoding="utf-8") as fh:
            json.dump(card(doc), fh, indent=1)
    elif os.path.exists(card_path):
        os.remove(card_path)                                # no passed gate = no card
    say(doc["line"])
    return doc


def trial_row(doc=None):
    """The Brain 'ideas on trial' row (tools/build_brain_learn.forward_rows shape)."""
    doc = doc if doc is not None else _read(OUT)
    if not isinstance(doc, dict) or "stats" not in doc:
        return None
    s = doc["stats"]
    st = {"watching": "watching", "waiting": "watching", "passed": "promote", "ask_owner": "promote", "stopped": "demoted"}.get(doc["status"], "watching")
    need = G0_N if doc["step"] == 0 else (G1_N if doc["step"] == 1 else G2_N)
    n = s["n"] if doc["step"] != 1 else 0
    left = max(0, need - n)
    eta = int(-(-left // RATE)) if left else 0
    word = {"promote": "ready: the lead writes your yes/no card", "demoted": "stopped: stays paper (its pre-set stop rule)"}.get(
        st, f"step {doc['step']} ({doc['step_name']}): needs {left} more forward trades (~{eta} trading days)")
    return {"id": "of_lane_a_ladder", "what": "Order flow lane A (absorption level fade) gate ladder: paper -> Sim101 -> one eval -> the rest -> funded",
            "bot": "OF", "kind": "ladder", "n": n, "need": need, "fwd_r": s["mean_R"], "fwd_sum": s["sum_R"], "band_r": 0.495,
            "band_n": 40, "z": None, "status": st, "eta_days": eta if st == "watching" else None, "word": word,
            "progress": round(min(1.0, n / need), 3) if need else 1.0}


def main(argv=None):
    run()


if __name__ == "__main__":
    main(sys.argv[1:])
