"""ZEUS Lab (owner 2026-11-18: "I want our strategies to keep getting stronger. Make a spot where the bot continues to learn as a
whole from each, and changes and adapts if it needs to."). docs/ZEUS_LAB.md (plain words).

A SAFE adaptive loop, not a self-modifying bot. RESEARCH ONLY: it never trades, never routes, never edits a live file
(live_model*.json, second_model.json, data/account_b.json are hashed before and after every run, engine/learn_loop.PROTECTED).
Adoption is a human step: the owner says yes, then Claude runs the CLAUDE.md steps (live_model.json + live_model_lit.json
together, `python tools/lit_losses.py live`, `python tools/model_versions.py`).

Built on what exists (nothing re-implemented):
  registry   research/lab/zeus_lab/registry.json (tracked): every candidate change for Zlarior (LIT) and ATLAS, written down
             before it is judged, + "rejected_forever" (the CLAUDE_REFERENCE "Tested and rejected" list + the learn loop's
             first 8: NEVER run again; a "blocks" entry stops any experiment on that bot + feature, cross ones too).
  members    kind atlas_member = a NEW ATLAS member (tools/atlas_plus.py, its stored verdict; "cells" = versions searched).
  anatomy    kind anatomy = a rule from the win / loss anatomy (tools/win_loss_anatomy.py: a size x m or a skip on an entry
             fact the trade-intel table does not hold, e.g. the daily x 1h trend pullback or the careful-human checklist), run
             by that tool's lab_run on the same real backtests and judges (Zlarior or ATLAS).
  funded     kind atlas_funded = a protective rule family on ATLAS's FUNDED 25K (tools/atlas_health.py, its stored verdict:
             member pause / edge-light size / day loss cap / smaller risk in a hole / skips; the family's Jan-Jun pick, the
             funded gate incl. the live stuck stop, and it must act in Jul-Oct; "cells" = versions scored).
  grade      kind setup_grade = the human setup grade A / B / C for Zlarior or ATLAS (tools/setup_grade.py, its stored
             verdict research/lab/setup_grade.json; "variant" = which grade + use, "cells" = every variant it tried).
  re-test    the REAL backtests through engine/learn_loop's runners: LIT = tools/lit_edge.evaluate (run lit_live re-walked:
             the LIT size + the live two_week eval path, costs in); ATLAS = tools/atlas_deep.score (the real account-B rules,
             engine/second.py members). Kinds: lit_tilt / atlas_tilt (the learn-loop rule language), lit_x (a
             tools/lit_edge management variant, e.g. the afternoon target cap) and lit_idea (tools/lit_lab_ideas: exit
             rules such as a time stop / NY-open guard / news exit, or two-fact size rules). On the PC the bars include the newest weeks
             (the data pipe), so every night re-tests on more data.
  proof      the project gates (engine/learn_loop.judge_lit / judge_atlas: picked on 2026 Jan-Jun, checked on Jul-Oct, both
             better, eval 2-week fails not up, 2-4 trades a week for LIT, 2021-25 shown (a gate for ATLAS), costs in, enough
             trades changed, the learn loop's 200-draw size shuffle for LIT tilts) PLUS two Lab guards:
               placebo     a sign-flip test on the per-trade $ changes (is the gain more than noise?), per half;
               many tests  family-wise alpha 0.2 split over every cell ever run here + the learn queue (Bonferroni):
                           with 14 cells each needs p <= 0.014 in BOTH halves.
  shadow     a passing experiment starts a SHADOW paper ledger on its first pass day: only trades on LATER days count
             (forward, never used to pick). READY TO ADOPT = proof still passing + N weeks of shadow (registry rules) + at
             least 2 forward trades changed + forward $ not below 0. Forward $ below 0 after N weeks = rejected.
  cross      every LIT tilt is tried on ATLAS and vice versa where the fact exists on both (vix, stop_atr, rr), unless that
             bot + fact is in rejected_forever.
  safety     the edge-health light (tools/edge_health.py -> research/lab/edge_health.json): RED = the Lab RECOMMENDS a
             size-down for the owner (no auto stop: the drift switch was tested and rejected 0/51); the approved guards
             (ATLAS zombie-eval rule, Rapid 30% best-day guard, lifecycle stand-downs) keep running as they are.
  notify     READY or RED (once each): engine/board_events.emit("claude_note") + one push on the PC's private ntfy topic
             ("ZEUS Lab: X passed. Reply yes to adopt"). Only from the nightly run (--notify) and only if no live file moved.
  page       tools/web_public/business/lab.html reads lab_pc.json (the PC's nightly copy, gitignored) else lab.json (the
             published copy, `publish`).

    python -X utf8 tools/zeus_lab.py run [--only id,id] [--notify] [--publish]   # re-test everything now (~1-3 min)
    python -X utf8 tools/zeus_lab.py status                                    # the table from the last run
    python -X utf8 tools/zeus_lab.py publish                                   # the last run -> business/lab.json
    python -X utf8 -m tests.test_zeus_lab                                      # offline checks (no data run)
Nightly: engine/learn_loop.run calls nightly(C) after its own experiments (same child, same bases, LE_LAB=0 turns it off).
Machine-local outputs: research/lab/zeus_lab/out/ (gitignored: the PC's auto-update needs a clean tree).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

LAB_DIR = os.path.join(ROOT, "research", "lab", "zeus_lab")
REGISTRY = os.path.join(LAB_DIR, "registry.json")
OUT_DIR = os.path.join(LAB_DIR, "out")                                       # gitignored (machine-local)
PAGE_PUB = os.path.join(ROOT, "tools", "web_public", "business", "lab.json")      # tracked, the published copy
PAGE_PC = os.path.join(ROOT, "tools", "web_public", "business", "lab_pc.json")    # gitignored, the PC's nightly copy
REF_DOC = os.path.join(ROOT, "docs", "TESTED_AND_REJECTED.md")   # moved out of CLAUDE_REFERENCE.md 2026-11-18
EDGE = os.path.join(ROOT, "research", "lab", "edge_health.json")
ZEUS_QUEUE = os.path.join(ROOT, "research", "zeus_queue.jsonl")         # night-learn's daily review proposals (tools/data_pull.py)
VERSION = 1
RUNNABLE = ("lit_tilt", "atlas_tilt", "lit_x", "atlas_member", "lit_idea", "atlas_funded", "anatomy", "setup_grade")
FUNDED_FAMILIES = ("M", "L", "D", "S", "K")   # tools/atlas_health.FAMILY
GRADE_VARIANTS = ("h1:skipC", "h1:size", "all7:skipC", "all7:size")          # tools/setup_grade.py
CELL_KINDS = ("atlas_member", "atlas_funded", "setup_grade")                  # kinds that count every version they searched
KINDS = RUNNABLE + ("parked",)
BOTS = ("lit", "atlas", "kalshi")
LIT_X_KEYS = ("tgt", "be", "tc", "speed", "slow", "late")
STATUS_WORD = {"testing": "Testing", "shadow": "Shadow (paper, forward)", "ready": "READY TO ADOPT", "rejected": "Rejected",
               "parked": "Parked (not built)", "forever": "Rejected for good", "adopted": "Adopted", "error": "Error",
               "blocked": "Rejected for good (already tested)", "proposed": "Proposed by the bot (to be written as a test)"}
DEFAULT_RULES = {"shadow_weeks": 4, "min_forward_changed": 2, "family_alpha": 0.2, "signflip_draws": 4000, "atlas_risk_usd": 250}
CROSS = {("lit", "atlas"): {"vix": "vix", "stop_atr": "stop_atr", "rr": "rr"},
         ("atlas", "lit"): {"vix": "vix", "stop_atr": "stop_atr", "rr": "rr"}}
TILT_OF = {"lit": "lit_tilt", "atlas": "atlas_tilt"}
NAME = {"lit": "Zlarior", "atlas": "ATLAS", "kalshi": "Kalshi"}
LIT_SPAN_MONTHS = {"H1": 6.0, "H2": None, "2021-25": 60.0}


# ================================================================================================ small helpers
def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write_json(path, obj, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=indent, default=str)
    os.replace(tmp, path)


def _num(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def money(x) -> str:
    x = _num(x)
    if x is None:
        return "-"
    return ("-" if x < 0 else "+") + f"${abs(x):,.0f}"


def _features(rule) -> set:
    return {s.get("feature") for s in (rule or []) if isinstance(s, dict)}


# ================================================================================================ the registry
def load_registry(path: str = REGISTRY) -> tuple:
    """(experiments, rejected_forever, rules, errors). Invalid experiments are left out and named."""
    from engine import learn_loop as LL
    R = _read_json(path, None)
    if not isinstance(R, dict) or not isinstance(R.get("experiments"), list):
        return [], [], dict(DEFAULT_RULES), ["registry missing or not {experiments: [...]}"]
    rules = {**DEFAULT_RULES, **(R.get("rules") or {})}
    forever = [f for f in (R.get("rejected_forever") or []) if isinstance(f, dict) and f.get("id")]
    out, errs, seen = [], [], set()
    for e in R["experiments"]:
        if not isinstance(e, dict) or not e.get("id"):
            errs.append("an experiment without an id")
            continue
        er = []
        if e["id"] in seen:
            er.append("duplicate id")
        if e.get("kind") not in KINDS:
            er.append(f"unknown kind {e.get('kind')!r}")
        if e.get("bot") not in BOTS:
            er.append("bot must be lit, atlas or kalshi")
        for k in ("title", "what_changes", "registered", "source"):
            if not e.get(k):
                er.append(f"needs {k}")
        if e.get("kind") in ("lit_tilt", "atlas_tilt"):
            er += LL.rule_errors(e.get("rule"))
            if TILT_OF.get(e.get("bot")) != e.get("kind"):
                er.append("kind does not match bot")
        if e.get("kind") == "lit_x":
            x = e.get("x")
            if not isinstance(x, dict) or not x or any(k not in LIT_X_KEYS for k in x):
                er.append(f"x must be a dict of {LIT_X_KEYS}")
            if e.get("bot") != "lit":
                er.append("lit_x is for bot lit")
        if e.get("kind") == "lit_idea":
            from tools import lit_lab_ideas as LI
            er += LI.idea_errors(e.get("idea"))
            if e.get("bot") != "lit":
                er.append("lit_idea is for bot lit")
        if e.get("kind") == "anatomy":
            from tools import win_loss_anatomy as WA
            er += WA.rule_errors(e)
        if e.get("kind") == "atlas_member" and (e.get("bot") != "atlas" or not e.get("family")):
            er.append("atlas_member is for bot atlas and needs family (tools/atlas_plus.py)")
        if e.get("kind") == "atlas_funded" and (e.get("bot") != "atlas" or e.get("family") not in FUNDED_FAMILIES):
            er.append(f"atlas_funded is for bot atlas and needs family in {FUNDED_FAMILIES} (tools/atlas_health.py)")
        if e.get("kind") == "setup_grade" and (e.get("bot") not in ("lit", "atlas") or e.get("variant") not in GRADE_VARIANTS):
            er.append(f"setup_grade is for bot lit or atlas and needs variant in {GRADE_VARIANTS} (tools/setup_grade.py)")
        if e.get("kind") == "parked" and not e.get("parked_why"):
            er.append("a parked experiment needs parked_why")
        if er:
            errs.append(f"{e['id']}: " + "; ".join(er))
            continue
        seen.add(e["id"])
        if e.get("on", True):
            out.append(e)
    return out, forever, rules, errs


def register(e: dict, path: str = REGISTRY, replace: bool = True) -> list:
    """Write one experiment into the registry (validated the way load_registry reads it). Returns the errors ([] = saved).
    replace: an experiment with the same id is replaced (its registered date kept)."""
    R = _read_json(path, None)
    if not isinstance(R, dict) or not isinstance(R.get("experiments"), list):
        return ["registry missing or not {experiments: [...]}"]
    old = next((x for x in R["experiments"] if x.get("id") == e.get("id")), None)
    if old is not None and not replace:
        return [f"{e.get('id')}: already registered"]
    e = {**e, "registered": (old or {}).get("registered") or e.get("registered")}
    exps = [x for x in R["experiments"] if x.get("id") != e.get("id")] + [e]
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tp = os.path.join(td, "r.json")
        _write_json(tp, {**R, "experiments": exps}, indent=1)
        _, _, _, errs = load_registry(tp)
    errs = [x for x in errs if x.startswith(f"{e.get('id')}:") or "without an id" in x]
    if errs:
        return errs
    txt = open(path, encoding="utf-8").read()
    # keep the hand-kept layout (night-bugsweep 2026-11-19: a replace used to rewrite the whole file in json.dump's layout): a new entry
    # is one new line at the end of "experiments"; a replaced one becomes one line in its own place; every other byte stays as it was
    new = None
    try:
        close, spans = _array_spans(txt, "experiments")
        line = json.dumps(e, ensure_ascii=False)
        hit = next(((a, b) for a, b, x in spans if isinstance(x, dict) and x.get("id") == e.get("id")), None) if old is not None else None
        if hit:
            new = txt[:hit[0]] + line + txt[hit[1]:]
            want = [e if x.get("id") == e.get("id") else x for x in R["experiments"]]
        else:
            k = len(txt[:close].rstrip())
            new = txt[:k] + ("," if spans else "") + "\n  " + line + "\n " + txt[close:]
            want = exps
        if json.loads(new).get("experiments") != want:
            new = None
    except (ValueError, KeyError):
        new = None
    if new is None:                       # a file this cannot splice (hand-edited oddly): the plain layout, still valid
        R["experiments"] = exps
        _write_json(path, R, indent=1)
        return []
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(new)
    os.replace(tmp, path)
    return []


def _array_spans(txt: str, key: str) -> tuple:
    """(index of the closing "]", [(start, end, value) of each element]) of the top-level array `key` in a JSON text."""
    i = txt.index("[", txt.index(f'"{key}"'))
    dec, pos, out = json.JSONDecoder(), i + 1, []
    while True:
        pos = re.compile(r"[\s,]*").match(txt, pos).end()
        if txt[pos] == "]":
            return pos, out
        val, end = dec.raw_decode(txt, pos)
        out.append((pos, end, val))
        pos = end


def doc_rejected(path: str = REF_DOC) -> list:
    """The bold heads of CLAUDE_REFERENCE 'Tested and rejected' (shown on the page as rejected for good, never re-run)."""
    try:
        txt = open(path, encoding="utf-8").read()
    except OSError:
        return []
    m = re.search(r"^## Tested and rejected.*?$(.*?)(?=^## |\Z)", txt, re.S | re.M)
    body = m.group(1) if m else txt
    out = []
    for h in re.findall(r"^- \*\*(.+?)\*\*", body, re.M):
        h = re.sub(r"\s*\(.*$", "", h).rstrip(":").strip()
        if h and h not in out:
            out.append(h)
    return out


def blocked_by(e: dict, forever: list):
    """The rejected_forever entry that rules this experiment out (same id, or a block on its bot + one of its facts)."""
    feats = _features(e.get("rule"))
    for f in forever:
        if f["id"] == e["id"]:
            return f
        b = f.get("blocks") or {}
        if b and b.get("bot") == e.get("bot") and b.get("feature") in feats:
            return f
    return None


def cross_experiments(exps: list, forever: list) -> list:
    """Cross-learning: each tilt tried on the other bot where every fact it uses exists there (same cut rule: an h1_q cut is
    re-picked on the other bot's own Jan-Jun trades). Blocked ones come back marked, never run."""
    have = {e["id"] for e in exps}
    out = []
    for e in exps:
        if e.get("kind") not in ("lit_tilt", "atlas_tilt") or e.get("cross") is False or blocked_by(e, forever):
            continue
        other = "atlas" if e["bot"] == "lit" else "lit"
        fmap = CROSS[(e["bot"], other)]
        if not _features(e["rule"]) <= set(fmap):
            continue
        cid = f"{e['id']}__on_{other}"
        if cid in have:
            continue
        rule = [{**s, "feature": fmap[s["feature"]]} for s in e["rule"]]
        title = e["title"].split(":", 1)[-1].strip()
        c = {"id": cid, "bot": other, "kind": TILT_OF[other], "registered": e["registered"], "origin": "cross",
             "cross_of": e["id"], "source": f"cross from {e['id']} ({NAME[e['bot']]})", "rule": rule,
             "title": f"{NAME[other]}: {title} (learned from {NAME[e['bot']]})",
             "what_changes": e["what_changes"].replace(NAME[e["bot"]], NAME[other]),
             "hypothesis": f"What may help {NAME[e['bot']]} tried on {NAME[other]}: " + (e.get("hypothesis") or ""),
             "judged_by": TILT_OF[other]}
        out.append(c)
    return out


def cells(exps: list, queue_n: int = 0) -> int:
    """Cells ever judged in this search: every runnable Lab experiment (cross ones too) + the learn queue. An atlas_member
    or atlas_funded family or setup_grade entry counts every version its tool searched ("cells")."""
    return sum(int(e.get("cells") or 1) if e.get("kind") in CELL_KINDS else 1 for e in exps if e.get("kind") in RUNNABLE) + int(queue_n)


def p_needed(n_cells: int, alpha: float = 0.2) -> float:
    return round(alpha / max(1, int(n_cells)), 5)


# ================================================================================================ the placebo (pure)
def signflip_p(deltas, n: int = 4000, seed: int = 7) -> float:
    """One-sided sign-flip test: share of random +/- sign draws of the per-trade $ changes whose sum is at least the real
    sum ((k+1)/(n+1)). No change or a loss = 1.0."""
    import numpy as np
    d = np.array([float(x) for x in deltas if _num(x) is not None and abs(float(x)) > 1e-9])
    if not len(d) or d.sum() <= 0:
        return 1.0
    rng = np.random.default_rng(seed)
    real = d.sum()
    k, done, step = 0, 0, 1000
    while done < n:
        m = min(step, n - done)
        S = (rng.choice((-1.0, 1.0), size=(m, len(d))) * d).sum(axis=1)
        k += int((S >= real - 1e-9).sum())
        done += m
    return round((k + 1) / (n + 1), 5)


def span_of(day: str, bot: str) -> str:
    if "2026-01-01" <= day <= "2026-06-30":
        return "H1"
    if day >= "2026-07-01":
        return "H2"
    if bot == "atlas":
        return "2025" if day >= "2025-01-01" else "2021-24"
    return "2021-25"


# ================================================================================================ the runners (real data)
def _lit_deltas(L, L0) -> list:
    b = {int(l["entry_t"]): l for l in L0}
    n = {int(l["entry_t"]): l for l in L}
    out = []
    for k in sorted(set(b) | set(n)):
        x, y = n.get(k), b.get(k)
        d = float((x or {}).get("pnl") or 0) - float((y or {}).get("pnl") or 0)
        if abs(d) > 0.5:
            out.append({"day": (x or y)["day"], "t": k, "usd": round(d, 2)})
    return out


def run_lit(e: dict, C, rules: dict) -> dict:
    """lit_tilt (a size rule), lit_x (a management variant) or lit_idea (tools/lit_lab_ideas: an exit or size idea the rule
    language cannot say) through tools/lit_edge + the learn loop's LIT judge."""
    from engine import learn_loop as LL
    from tools import lit_edge as E
    o0, U0, L0, s0 = C.lit_base()
    if e["kind"] == "lit_tilt":
        rule = LL.resolve(e["rule"], E.h1_cut)
        o, U, L = E.evaluate(mfn=lambda t, row: LL.rule_mult(rule, row))
        hits = {}
        intel = E.ctx()["intel"]
        for t in E.ctx()["T"]:
            if LL.rule_mult(rule, intel.get(int(t["entry_t"]), {})) != 1.0:
                sp = LL._span_lit(t["day"])
                hits[sp] = hits.get(sp, 0) + 1
    elif e["kind"] == "lit_idea":                                               # tools/lit_lab_ideas (exit / size ideas)
        from tools import lit_lab_ideas as LI
        rule = None
        with LI.eval_hook(e["idea"]):                                           # eval ideas: the eval path's sizing
            o, U, L = E.evaluate(U=LI.units(e["idea"]))
        hits = LI.hits(e["idea"], U, U0)
    else:
        rule = None
        o, U, L = E.evaluate(X=e["x"])
        hits = E.changed(L, L0)
    tilt = e["kind"] == "lit_tilt" or (e["kind"] == "lit_idea" and e["idea"]["name"] in _lit_size_ideas())
    s = E.short(o, o0)
    D = _lit_deltas(L, L0)
    flip = {h: signflip_p([d["usd"] for d in D if span_of(d["day"], "lit") == h], rules["signflip_draws"]) for h in ("H1", "H2")}
    pre = LL.judge_lit(s, s0, hits, None)
    plc = None
    if tilt and not pre["why"].startswith("too few") and E.gate(s):
        plc = E.placebo(U, L0, n=LL.PLACEBO_N)                                   # the learn loop's size shuffle
    v = LL.judge_lit(s, s0, hits, plc if tilt else flip) if (plc is not None or not tilt) else pre
    return {"rule": rule, "hits": hits, "shuffle": plc, "flip": flip, "head": LL._lit_head(s), "base": LL._lit_head(s0),
            "deltas": D, "proof_ok": v["status"] == "candidate", "why": v["why"], "usd_month_by": v["usd_month_by"],
            "eval_usd_month_by": v.get("eval_usd_month_by")}


def _lit_size_ideas():
    from tools import lit_lab_ideas as LI
    return LI.SIZE_IDEAS


def run_atlas(e: dict, C, rules: dict) -> dict:
    """atlas_tilt through engine/learn_loop.run_atlas_tilt (tools/atlas_deep.score, the real account-B rules) + per-trade
    fixed-risk $ changes for the placebo and the shadow ledger ((m - 1) x R x the funded 25K's $ a trade)."""
    from engine import learn_loop as LL
    r = LL.run_atlas_tilt(e, C)
    o0, U, F = C.atlas_base()
    risk = float(rules["atlas_risk_usd"])
    D = []
    for f in F:
        m = LL.rule_mult(r["rule"], f)
        R = _num(f.get("R"))
        if m != 1.0 and R is not None:
            D.append({"day": f["day"], "t": f"{f.get('src')}:{f['day']}:{f.get('hour')}", "usd": round((m - 1.0) * R * risk, 2)})
    flip = {h: signflip_p([d["usd"] for d in D if span_of(d["day"], "atlas") == h], rules["signflip_draws"]) for h in ("H1", "H2")}
    why = r["why"]
    extra = atlas_why(r["head"], r["base"])
    if r["status"] != "candidate" and extra:
        why = f"{why} ({extra})"
    return {"rule": r["rule"], "hits": r["hits"], "flip": flip, "head": r["head"], "base": r["base"], "deltas": D,
            "proof_ok": r["status"] == "candidate", "why": why, "usd_month_by": r["usd_month_by"], "verdict_v2": r.get("verdict_v2")}


def atlas_why(h: dict, b: dict) -> str:
    """Which part of ATLAS's half test failed (tools/atlas_v2.better2026: 2-week pass not down, dead evals not up, $ up)."""
    nm = {"H1": "Jan-Jun", "H2": "Jul-Oct"}
    out = []
    for sp in ("H1", "H2"):
        x, y = (h or {}).get(sp) or {}, (b or {}).get(sp) or {}
        p, p0, d, d0 = _num(x.get("p10")), _num(y.get("p10")), _num(x.get("dead10")), _num(y.get("dead10"))
        m, m0 = _num(x.get("mp_net_less_fees")), _num(y.get("mp_net_less_fees"))
        if p is not None and p0 is not None and p < p0:
            out.append(f"{nm[sp]} 2-week pass {p0:g} -> {p:g}%")
        if d is not None and d0 is not None and d > d0:
            out.append(f"{nm[sp]} dead evals {d0:g} -> {d:g}%")
        if m is not None and m0 is not None and m <= m0:
            out.append(f"{nm[sp]} money after fees {money(m - m0)}")
    return "; ".join(out)


def run_member(e: dict, C, rules: dict) -> dict:
    """atlas_member: a NEW ATLAS member (tools/atlas_plus.py: alone at $250, coin-flip sides, days vs ATLAS / LIT, then as a
    member on the funded 25K Monte Carlo at $250 / 30% of the room). Reads that tool's stored verdict
    (research/second/atlas_plus.json); rerun the tool for new bars. The Lab adds its own sign-flip / many-tests guard."""
    from tools import atlas_plus as AP
    return AP.lab_result(e)


def run_funded(e: dict, C, rules: dict) -> dict:
    """atlas_funded: a protective rule family on ATLAS's funded 25K (tools/atlas_health.py: the funded Monte Carlo with the
    live stuck stop, from a fresh start and from today's balance, real day order, fixed-$250 view, random-timing control).
    Reads that tool's stored verdict (research/second/atlas_health.json; rerun the tool for new bars)."""
    from tools import atlas_health as AH
    return AH.lab_result(e)
def run_grade(e: dict, C, rules: dict) -> dict:
    """setup_grade: the human setup grade (tools/setup_grade.py: 7 checks a calm trader asks, A / B / C by the warnings
    count, skip C or size A / B / C; LIT size + eval path + 2021-25, ATLAS eval + funded 25K, random-grade luck test).
    Reads that tool's stored verdict (research/lab/setup_grade.json); rerun the tool for new bars."""
    from tools import setup_grade as SG
    return SG.lab_result(e)


def run_one(e: dict, C, rules: dict) -> dict:
    if e["kind"] == "anatomy":                                                 # tools/win_loss_anatomy.py (2026-11-18)
        from tools import win_loss_anatomy as WA
        return WA.lab_run(e, C, rules)
    if e["kind"] == "atlas_member":
        return run_member(e, C, rules)
    if e["kind"] == "atlas_funded":
        return run_funded(e, C, rules)
    if e["kind"] == "setup_grade":
        return run_grade(e, C, rules)
    return run_atlas(e, C, rules) if e["kind"] == "atlas_tilt" else run_lit(e, C, rules)


# ================================================================================================ proof + shadow (pure)
def proof(r: dict, thr: float) -> dict:
    """The full proof: the project gate (r['proof_ok']) + the sign-flip placebo under the many-tests threshold, both halves."""
    why = [] if r.get("proof_ok") else [r.get("why") or "project gate failed"]
    fl = r.get("flip") or {}
    if r.get("proof_ok"):
        bad = [h for h in ("H1", "H2") if float(fl.get(h, 1.0)) > thr]
        if bad:
            why.append("could be luck: " + ", ".join(f"{h} p {fl.get(h)}" for h in bad) + f" (needs <= {thr} with this many tests)")
    return {"ok": not why, "why": "; ".join(why) or "passes: better in Jan-Jun and Jul-Oct, costs in, beats random, survives the many-tests guard"}


def forward(deltas: list, since: str) -> dict:
    F = [d for d in deltas if d["day"] > since]
    return {"trades": len(F), "usd": round(sum(d["usd"] for d in F), 2), "last": [d for d in F][-10:]}


def weeks_between(a: str, b: str) -> float:
    try:
        return round((dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days / 7.0, 1)
    except (TypeError, ValueError):
        return 0.0


def step(prev: dict, pr: dict, deltas: list, data_day: str, rules: dict) -> dict:
    """The status machine of one runnable experiment. prev = its last state ({} the first time)."""
    st = prev.get("status")
    if st == "adopted":
        return {"status": "adopted", "shadow_from": prev.get("shadow_from")}
    if not pr["ok"]:
        out = {"status": "rejected", "why": pr["why"]}
        if prev.get("shadow_from"):
            out["was_shadow"] = {"from": prev["shadow_from"], **forward(deltas, prev["shadow_from"])}
        return out
    since = prev.get("shadow_from") if st in ("shadow", "ready") else None
    since = since or data_day
    fw = forward(deltas, since)
    wk = weeks_between(since, data_day)
    out = {"shadow_from": since, "shadow": {**fw, "weeks": wk}, "why": pr["why"]}
    if wk >= rules["shadow_weeks"] and fw["trades"] >= rules["min_forward_changed"]:
        if fw["usd"] >= 0:
            out["status"] = "ready"
            out["ready_since"] = prev.get("ready_since") if st == "ready" else data_day
        else:
            out.update(status="rejected", why=f"shadow lost {money(fw['usd'])} over {wk:g} weeks ({fw['trades']} trades)")
    else:
        out["status"] = "shadow"
        need = []
        if wk < rules["shadow_weeks"]:
            need.append(f"{rules['shadow_weeks'] - wk:g} more weeks")
        if fw["trades"] < rules["min_forward_changed"]:
            need.append(f"{rules['min_forward_changed'] - fw['trades']} more changed trades")
        out["needs"] = " and ".join(need)
    return out


# ================================================================================================ safety (edge health)
def safety(path: str = EDGE) -> dict:
    """The edge-health light -> the Lab's safety advice. RED = recommend a size-down for the owner; never an auto stop."""
    d = _read_json(path, None) or {}
    card = d.get("card") or {}
    light = (card.get("light") or ((d.get("light") or {}).get("now") or {}).get("light") or "").upper() or None
    out = {"light": light, "data_to": card.get("data_to"), "line": card.get("line")}
    if light == "RED":
        out["advice"] = "size_down"
        out["say"] = ("Edge light RED: Zlarior's last 40 sessions look like 2021-25 (no edge). Lab advice: hold off buying new "
                      "evals and consider half size on new evals (your yes needed). The bots keep trading their approved sizes; "
                      "nothing stops by itself.")
    elif light == "AMBER":
        out["advice"] = "watch"
        out["say"] = "Edge light AMBER: weaker than spring, not broken. No change; the Lab watches."
    elif light == "GREEN":
        out["advice"] = "none"
        out["say"] = "Edge light GREEN: the market still looks like 2026. No change."
    else:
        out["advice"] = "unknown"
        out["say"] = "Edge light not built on this machine yet (python tools/edge_health.py)."
    return out


# ================================================================================================ notify (PC only)
def ready_line(row: dict) -> str:
    u = row.get("usd_month_by") or {}
    return (f"ZEUS Lab: {row['title']} passed ({money(u.get('H1'))} / {money(u.get('H2'))} a month Jan-Jun / Jul-Oct, "
            f"shadow {money((row.get('shadow') or {}).get('usd'))}). Reply yes to adopt")


def notify(events: list, emit_fn=None, push_fn=None) -> list:
    """events = [(kind, text, data)]: one board line (claude_note) + one push each. Never raises."""
    sent = []
    for kind, text, data in events:
        ok_b = ok_p = False
        why = ""
        try:
            if emit_fn is None:
                from engine import board_events as BE
                emit_fn = BE.emit
            ok_b = bool(emit_fn("claude_note", "", text, data))
        except Exception as ex:  # noqa: BLE001
            why = f"board {ex.__class__.__name__}"
        try:
            if push_fn is None:
                from engine import learn_loop as LL
                push_fn = LL.push_phone
            ok_p, why2 = push_fn(text, title="ZEUS Lab")
            why = why or str(why2 or "")
        except Exception as ex:  # noqa: BLE001
            why = why or f"push {ex.__class__.__name__}"
        sent.append({"kind": kind, "text": text, "board": ok_b, "push": bool(ok_p), "why": why[:80]})
    return sent


# ================================================================================================ the bot's own ideas
def bot_proposals(path: str = ZEUS_QUEUE, have=(), n: int = 20) -> list:
    """The ZEUS daily review's proposals (engine/zeus_review.py on the PC -> research/zeus_queue.jsonl via tools/data_pull.py):
    shown as 'proposed' until Claude writes one as a registry experiment (then it is judged like every other). Never run here."""
    rows, seen = [], set(have)
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return []
    for ln in reversed(lines):
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        pid = str(r.get("id") or "")
        if not pid or pid in seen or r.get("status") not in (None, "new"):
            continue
        seen.add(pid)
        bot = r.get("bot") if r.get("bot") in BOTS else "lit"
        ev = r.get("evidence")
        rows.append({"id": pid, "bot": bot, "who": NAME.get(bot, bot), "title": str(r.get("what") or pid)[:160],
                     "what": str(r.get("what") or "")[:300], "source": f"ZEUS daily review {r.get('day') or ''}".strip(),
                     "origin": "bot", "status": "proposed", "word": STATUS_WORD["proposed"],
                     "why": (json.dumps(ev, default=str) if isinstance(ev, (dict, list)) else str(ev or ""))[:300]})
        if len(rows) >= n:
            break
    return rows


# ================================================================================================ the page
def _per_month_lit(h: dict, sp: str, key: str = None):
    x = (h or {}).get(sp) or {}
    if key:
        x = x.get(key) or {}
    return _num(x.get("per_month"))


def _atlas_ref(h: dict):
    a, b = _num(((h or {}).get("2025") or {}).get("per_month")), _num(((h or {}).get("2021-24") or {}).get("per_month"))
    if a is None or b is None:
        return None
    return round((a * 12 + b * 48) / 60.0)


def page_row(e: dict, s: dict, blocked=None) -> dict:
    """One experiment for the page, plain words, $ first."""
    row = {"id": e["id"], "bot": e["bot"], "who": NAME.get(e["bot"], e["bot"]), "title": e["title"], "what": e["what_changes"],
           "source": e.get("source"), "origin": e.get("origin"), "cross_of": e.get("cross_of"), "registered": e.get("registered")}
    if blocked:
        row.update(status="blocked", word=STATUS_WORD["blocked"], why=f"already tested: {blocked['title']} ({blocked.get('source')})")
        return row
    if e["kind"] == "parked":
        row.update(status="parked", word=STATUS_WORD["parked"], why=e.get("parked_why"))
        return row
    st = s.get("status") or "testing"
    row.update(status=st, word=STATUS_WORD.get(st, st), why=s.get("why"), needs=s.get("needs"), shadow=s.get("shadow"),
               shadow_from=s.get("shadow_from"), usd_month_by=s.get("usd_month_by"), flip=s.get("flip"), hits=s.get("hits"),
               tested=s.get("tested"), was_shadow=s.get("was_shadow"))
    h, b = s.get("head") or {}, s.get("base") or {}
    if e["bot"] == "lit":
        row["months"] = {sp: {"exp": _per_month_lit(h, sp), "now": _per_month_lit(b, sp)} for sp in ("H1", "H2", "2021-25")}
        row["eval_months"] = {sp: {"exp": _per_month_lit(h, sp, "eval"), "now": _per_month_lit(b, sp, "eval")} for sp in ("H1", "H2")}
        row["detail"] = {sp: {k: (h.get(sp) or {}).get(k) for k in ("n", "tpw", "pf", "net", "dd")} for sp in ("H1", "H2", "2021-25")}
        row["speed"] = {sp: {k: ((h.get(sp) or {}).get("eval") or {}).get(k) for k in ("p10", "f10", "pass_med")} for sp in ("H1", "H2")}
    else:
        row["months"] = {"H1": {"exp": _per_month_lit(h, "H1"), "now": _per_month_lit(b, "H1")},
                         "H2": {"exp": _per_month_lit(h, "H2"), "now": _per_month_lit(b, "H2")},
                         "2021-25": {"exp": _atlas_ref(h), "now": _atlas_ref(b)}}
        row["detail"] = {sp: {k: (h.get(sp) or {}).get(k) for k in ("n", "tpw", "pf", "net", "dd")} for sp in ("H1", "H2", "2025", "2021-24")}
        row["speed"] = {sp: {k: (h.get(sp) or {}).get(k) for k in ("p10", "f10", "pass_med")} for sp in ("H1", "H2")}
    return row


ORDER = {"ready": 0, "shadow": 1, "testing": 2, "proposed": 3, "error": 3, "rejected": 4, "parked": 5, "blocked": 6, "adopted": 7}


def build_page(S: dict) -> dict:
    rows = sorted(S.get("rows") or [], key=lambda r: (ORDER.get(r.get("status"), 9), r.get("bot") != "lit", r.get("id")))
    cnt = {}
    for r in rows:
        cnt[r["status"]] = cnt.get(r["status"], 0) + 1
    return {"v": VERSION, "t": S.get("t"), "built": S.get("built"), "data_to": S.get("data_to"), "where": S.get("where"),
            "counts": cnt, "cells": S.get("cells"), "p_needed": S.get("p_needed"), "rules": S.get("rules"),
            "safety": S.get("safety"), "recent": S.get("recent"), "rows": rows, "forever": S.get("forever"),
            "forever_doc": S.get("forever_doc"), "protected_ok": S.get("protected_ok"), "errors": S.get("errors"),
            "how": ["Every night on your PC (after the data comes in) the Lab re-tests each idea on the real Zlarior and ATLAS "
                    "backtests, all periods, costs in.",
                    "An idea must make more $ in Jan-Jun AND Jul-Oct, keep 2-4 trades a week, not raise eval fails, and beat "
                    "random luck (with a stricter bar the more ideas we test).",
                    "Then it trades on paper (shadow) for 4 weeks on days it has never seen. Still not losing = READY TO ADOPT: "
                    "you get one push. Nothing changes until you say yes.",
                    "What helps Zlarior is tried on ATLAS and the other way round. Ideas already rejected are never re-run."]}


# ================================================================================================ one run
def data_last_day(root: str = ROOT) -> str | None:
    """Newest 5m bar day (ET) of the data the backtest reads (data/NQ_5m.csv; the PC's pipe appends the newest weeks)."""
    p = os.path.join(root, "data", "NQ_5m.csv")
    try:
        with open(p, "rb") as fh:
            fh.seek(0, 2)
            n = fh.tell()
            fh.seek(max(0, n - 4096))
            last = fh.read().decode("utf-8", "ignore").strip().splitlines()[-1]
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(int(float(last.split(",")[0])), ZoneInfo("America/New_York")).date().isoformat()
    except (OSError, ValueError, IndexError):
        return None


def run(C=None, only=None, do_notify: bool = False, out_dir: str = OUT_DIR, registry: str = REGISTRY, root: str = ROOT,
        runner=None, now=None, data_day: str | None = None, page_path: str | None = None, emit_fn=None, push_fn=None,
        edge_path: str = EDGE, write: bool = True, say=print) -> dict:
    """Re-test every runnable experiment, move each through testing -> shadow -> ready / rejected, write the state, the page
    data and (do_notify) one board line + push per new READY or a new RED light. Never edits a live file (checked)."""
    from engine import learn_loop as LL
    t0 = time.monotonic()
    now = int(now if now is not None else time.time())
    h0 = LL.protected_hashes(root)
    C = C or LL.Ctx()
    exps, forever, rules, errs = load_registry(registry)
    exps = exps + cross_experiments(exps, forever)
    qn = len(LL.load_queue()[0]) if registry == REGISTRY else 0
    runnable = [e for e in exps if e["kind"] in RUNNABLE and not blocked_by(e, forever)]
    n_cells = cells(runnable, qn)
    thr = p_needed(n_cells, rules["family_alpha"])
    day = data_day or data_last_day(root) or dt.date.today().isoformat()
    st = _read_json(os.path.join(out_dir, "state.json"), {}) or {}
    prev_all = st.get("exps") or {}
    rows, events, errors = [], [], list(errs)
    for e in exps:
        b = blocked_by(e, forever)
        if b or e["kind"] == "parked":
            rows.append(page_row(e, {}, b))
            continue
        prev = prev_all.get(e["id"]) or {}
        if only and e["id"] not in only:
            rows.append(page_row(e, prev))
            continue
        t1 = time.monotonic()
        try:
            r = (runner or run_one)(e, C, rules)
            pr = proof(r, thr)
            s = step(prev, pr, r.get("deltas") or [], day, rules)
            s.update({k: r.get(k) for k in ("head", "base", "usd_month_by", "eval_usd_month_by", "flip", "hits", "shuffle")})
            s["tested"] = day
        except Exception as ex:  # noqa: BLE001
            s = {**prev, "status": "error", "why": f"{ex.__class__.__name__}: {ex}"[:200]}
            errors.append(f"{e['id']}: {s['why']}")
        s["took_s"] = round(time.monotonic() - t1, 1)
        if s.get("status") == "ready" and prev.get("status") != "ready":
            events.append(("ready", None, e, s))
        prev_all[e["id"]] = s
        rows.append(page_row(e, s))
        say(f"  {e['id']:34s} {s.get('status', '?'):9s} {s.get('took_s')}s  {str(s.get('why') or '')[:110]}")
    rows += bot_proposals(have={e["id"] for e in exps}) if registry == REGISTRY else []
    sf = safety(edge_path)
    if sf.get("light") == "RED" and (st.get("safety") or {}).get("light") != "RED":
        events.append(("red", sf["say"], None, None))
    ok = LL.protected_hashes(root) == h0
    if not ok:
        errors.append("a live file changed during the run: nothing sent, results not trusted")
    sent = []
    if do_notify and ok and events:
        ev = []
        for kind, text, e, s in events:
            if kind == "ready":
                row = next(r for r in rows if r["id"] == e["id"])
                ev.append(("ready", ready_line(row), {"lab": e["id"], "status": "ready"}))
            else:
                ev.append(("red", "ZEUS Lab safety: " + text, {"lab": "safety", "light": "RED"}))
        sent = notify(ev, emit_fn=emit_fn, push_fn=push_fn)
    recent = None
    rl = C.c.get("recent_lit") if hasattr(C, "c") else None
    if rl:
        recent = {"lit_trades": len(rl), "lit_net": round(sum(float(t.get("pnl") or 0) for t in rl), 2),
                  "last_day": max((t.get("day") or "") for t in rl)}
    S = {"v": VERSION, "t": now, "built": dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M"), "data_to": day,
         "where": "pc" if os.name == "nt" else "cloud", "cells": n_cells, "p_needed": thr, "rules": rules, "safety": sf,
         "rows": rows, "recent": recent, "forever": [{"id": f["id"], "title": f["title"], "source": f.get("source")} for f in forever],
         "forever_doc": doc_rejected(), "protected_ok": ok, "errors": errors[:20], "sent": sent,
         "took_s": round(time.monotonic() - t0, 1)}
    if write:
        st.update(v=VERSION, t=now, exps=prev_all, safety={"light": sf.get("light"), "t": now})
        _write_json(os.path.join(out_dir, "state.json"), st)
        _write_json(os.path.join(out_dir, "summary.json"), S, indent=1)
        with open(os.path.join(out_dir, "history.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": now, "data_to": day, "counts": build_page(S)["counts"], "sent": len(sent)}) + "\n")
        _write_json(page_path or (PAGE_PC if os.name == "nt" else os.path.join(out_dir, "lab.json")), build_page(S))
    return S


def nightly(C=None, say=lambda *_: None) -> dict | None:
    """engine/learn_loop.run's hook: the Lab after the learn loop's own experiments, same child + bases. Never raises."""
    try:
        if os.environ.get("LE_LAB") == "0":
            return None
        S = run(C=C, do_notify=True, say=say)
        return {"took_s": S["took_s"], "counts": build_page(S)["counts"], "sent": len(S["sent"]), "errors": S["errors"][:3]}
    except Exception as ex:  # noqa: BLE001
        return {"error": f"{ex.__class__.__name__}: {ex}"[:200]}


def publish(out_dir: str = OUT_DIR, path: str = PAGE_PUB) -> dict:
    S = _read_json(os.path.join(out_dir, "summary.json"), None)
    if not S:
        raise SystemExit("no run yet: python -X utf8 tools/zeus_lab.py run")
    P = build_page(S)
    _write_json(path, P, indent=1)
    return P


def table(P: dict) -> str:
    L = [f"ZEUS Lab  data to {P.get('data_to')}  cells {P.get('cells')}  p needed {P.get('p_needed')}  "
         f"safety {((P.get('safety') or {}).get('light'))}"]
    for r in P.get("rows") or []:
        m = r.get("months") or {}
        f = lambda sp: money(((m.get(sp) or {}).get("exp") or 0) - ((m.get(sp) or {}).get("now") or 0)) if m.get(sp) else "-"  # noqa: E731
        L.append(f"  {r['word'][:22]:22s} {r['who']:8s} {r['title'][:60]:60s} H1 {f('H1'):>7s} H2 {f('H2'):>7s} 21-25 {f('2021-25'):>7s}")
    return "\n".join(L)


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="tools/zeus_lab.py", description="ZEUS Lab: the safe adaptive loop (research only).")
    ap.add_argument("cmd", choices=("run", "status", "publish"), nargs="?", default="status")
    ap.add_argument("--only", default="")
    ap.add_argument("--notify", action="store_true", help="board line + push for a new READY / RED (the PC's nightly run)")
    ap.add_argument("--publish", action="store_true", help="also write tools/web_public/business/lab.json")
    a = ap.parse_args(argv)
    if a.cmd == "status":
        S = _read_json(os.path.join(OUT_DIR, "summary.json"), None)
        print(table(build_page(S)) if S else "no run yet: python -X utf8 tools/zeus_lab.py run")
        return 0
    if a.cmd == "publish":
        print(table(publish()))
        return 0
    only = {x.strip() for x in a.only.split(",") if x.strip()} or None
    S = run(only=only, do_notify=a.notify)
    P = publish() if a.publish else build_page(S)
    print(table(P))
    print(f"took {S['took_s']}s, live files untouched: {S['protected_ok']}, errors: {len(S['errors'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
