"""ZEUS Lab (tools/zeus_lab.py): fast offline checks, no data run, no browser, no network.

  * the committed registry is valid: runnable seeds (LIT + ATLAS, the VIX < 15 lead), parked ones (Kalshi 5c pause, Asia $300),
    rejected_forever (the learn loop's first 8 + feature blocks), cross experiments made and the blocked ones never run
  * the placebo (sign flip) and the many-tests guard (alpha / cells)
  * the status machine: testing -> shadow (forward only) -> READY after N weeks + forward trades + forward $ >= 0;
    shadow lost -> rejected; proof broken -> rejected (shadow kept as history); adopted stays adopted
  * safety: RED -> size-down advice (never a stop), GREEN / AMBER / missing
  * one run with a fake runner in a temp dir: state + page, ONE board line + push for a NEW ready (not again), one for a
    new RED, none when not asked; a live file changed = nothing sent
  * static: never writes a live file, no broker / order import, outputs gitignored, the page reads only via textContent

    python -X utf8 -m tests.test_zeus_lab
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import zeus_lab as Z  # noqa: E402

RES = []
RULES = dict(Z.DEFAULT_RULES)


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"   -> {str(info)[:300]}"))


def t_registry():
    E, F, R, errs = Z.load_registry()
    ids = {e["id"] for e in E}
    check("registry loads without errors", not errs, errs)
    check("seeds: ATLAS VIX<15 skip, a LIT x variant, Kalshi 5c pause, Asia $300", {"atlas_skip_vix15", "lit_pm_cap_3r", "kalshi_pause_5c", "asia_slot_300"} <= ids, ids)
    check("both bots have runnable experiments", {e["bot"] for e in E if e["kind"] in Z.RUNNABLE} >= {"lit", "atlas"})
    check("learn loop's 8 are rejected forever", {"lit_gex_low_x1.25", "atlas_chop_day_x0.5", "lit_fast_fill_x1.25"} <= {f["id"] for f in F})
    check("no registry experiment is itself rejected forever", not [e for e in E if Z.blocked_by(e, F) and e.get("origin") != "cross"])
    X = Z.cross_experiments(E, F)
    xid = {x["id"] for x in X}
    check("cross: ATLAS VIX rule tried on Zlarior", "atlas_skip_vix15__on_lit" in xid, xid)
    check("cross: Zlarior R:R rule tried on ATLAS", "lit_rr_high_x1.25__on_atlas" in xid, xid)
    vx = next(x for x in X if x["id"] == "atlas_skip_vix15__on_lit")
    check("cross on Zlarior + VIX is blocked (VIX level already rejected for LIT)", bool(Z.blocked_by(vx, F)))
    check("cross on ATLAS R:R is not blocked", not Z.blocked_by(next(x for x in X if x["id"] == "lit_rr_high_x1.25__on_atlas"), F))
    check("cross keeps the cut rule, maps the bot + kind", vx["kind"] == "lit_tilt" and vx["rule"][0]["value"] == 15 and vx["bot"] == "lit")
    check("parked ones say why", all(e.get("parked_why") for e in E if e["kind"] == "parked"))
    tmp = tempfile.mkdtemp(prefix="zlab_reg_")
    try:
        p = os.path.join(tmp, "r.json")
        json.dump({"experiments": [{"id": "a", "bot": "lit", "kind": "lit_tilt", "title": "t", "what_changes": "w", "registered": "d", "source": "s",
                                    "rule": [{"feature": "vix", "op": "<", "mult": 9}]},
                                   {"id": "b", "bot": "atlas", "kind": "lit_x", "title": "t", "what_changes": "w", "registered": "d", "source": "s", "x": {"zzz": 1}},
                                   {"id": "c", "bot": "lit", "kind": "parked", "title": "t", "what_changes": "w", "registered": "d", "source": "s"}]}, open(p, "w"))
        E2, _, _, errs2 = Z.load_registry(p)
        check("bad rows left out and named (rule, x keys, parked_why)", not E2 and len(errs2) == 3, errs2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("CLAUDE_REFERENCE Tested and rejected heads parsed", len(Z.doc_rejected()) >= 10, Z.doc_rejected()[:3])


def t_placebo():
    check("sign flip: all-positive big gains -> small p", Z.signflip_p([100.0] * 12, 2000) < 0.01)
    check("sign flip: a loss -> 1.0", Z.signflip_p([-50, 10, 5], 500) == 1.0)
    check("sign flip: no change -> 1.0", Z.signflip_p([], 500) == 1.0 and Z.signflip_p([0, 0], 500) == 1.0)
    check("sign flip: one lucky trade among noise -> not significant", Z.signflip_p([300, -250, 280, -260, 20], 2000) > 0.1)
    check("many-tests guard: 0.2 / 14 cells", Z.p_needed(14, 0.2) == round(0.2 / 14, 5))
    check("cells count runnable + queue", Z.cells([{"kind": "lit_tilt"}, {"kind": "parked"}, {"kind": "atlas_tilt"}], 8) == 10)
    good = {"proof_ok": True, "flip": {"H1": 0.001, "H2": 0.004}}
    check("proof: gate + flip under threshold = ok", Z.proof(good, 0.014)["ok"])
    check("proof: flip above the many-tests bar = could be luck", not Z.proof({"proof_ok": True, "flip": {"H1": 0.001, "H2": 0.05}}, 0.014)["ok"])
    check("proof: gate failed = not ok, why kept", Z.proof({"proof_ok": False, "why": "Jan-Jun worse"}, 0.014)["why"] == "Jan-Jun worse")


def t_step():
    ok, bad = {"ok": True, "why": "passes"}, {"ok": False, "why": "Jul-Oct worse"}
    D = [{"day": "2026-03-02", "usd": 50}, {"day": "2026-11-20", "usd": 40}, {"day": "2026-12-01", "usd": 30}]
    s1 = Z.step({}, ok, D, "2026-11-18", RULES)
    check("first pass -> shadow from the data day", s1["status"] == "shadow" and s1["shadow_from"] == "2026-11-18" and s1["shadow"]["weeks"] == 0, s1)
    s2 = Z.step(s1, ok, D, "2026-12-02", RULES)
    check("forward only: trades after the start count", s2["shadow"]["trades"] == 2 and s2["shadow"]["usd"] == 70 and s2["status"] == "shadow", s2)
    check("shadow says what it still needs", "weeks" in (s2.get("needs") or ""), s2)
    s3 = Z.step(s2, ok, D, "2026-12-17", RULES)
    check("4 weeks + 2 forward trades + forward $ >= 0 -> READY", s3["status"] == "ready" and s3["ready_since"] == "2026-12-17", s3)
    s4 = Z.step(s3, ok, D, "2026-12-24", RULES)
    check("ready keeps its first ready day", s4["status"] == "ready" and s4["ready_since"] == "2026-12-17")
    DL = [{"day": "2026-11-20", "usd": -40}, {"day": "2026-12-01", "usd": -30}]
    s5 = Z.step(s2, ok, DL, "2026-12-17", RULES)
    check("shadow lost after 4 weeks -> rejected", s5["status"] == "rejected" and "shadow lost" in s5["why"], s5)
    s6 = Z.step(s2, bad, D, "2026-12-03", RULES)
    check("proof broken on new data -> rejected, shadow kept as history", s6["status"] == "rejected" and s6["was_shadow"]["from"] == "2026-11-18", s6)
    check("adopted stays adopted", Z.step({"status": "adopted"}, bad, D, "2026-12-03", RULES)["status"] == "adopted")
    s7 = Z.step(s6, ok, D, "2026-12-03", RULES)
    check("passing again restarts the shadow clock (no credit for old weeks)", s7["status"] == "shadow" and s7["shadow_from"] == "2026-12-03")


def _edge(tmp, light):
    p = os.path.join(tmp, f"edge_{light}.json")
    json.dump({"card": {"light": light, "data_to": "2026-11-06", "line": "x"}}, open(p, "w"))
    return p


def t_safety(tmp):
    r = Z.safety(_edge(tmp, "RED"))
    check("RED -> size-down advice", r["advice"] == "size_down" and "half size" in r["say"])
    check("RED never stops a bot by itself", "nothing stops by itself" in r["say"])
    check("GREEN -> no change", Z.safety(_edge(tmp, "GREEN"))["advice"] == "none")
    check("AMBER -> watch", Z.safety(_edge(tmp, "AMBER"))["advice"] == "watch")
    check("missing file -> unknown", Z.safety(os.path.join(tmp, "nope.json"))["advice"] == "unknown")


def _reg(tmp):
    p = os.path.join(tmp, "registry.json")
    base = {"title": "Zlarior: test idea", "what_changes": "w", "registered": "2026-11-18", "source": "s"}
    json.dump({"rules": {"signflip_draws": 500}, "experiments": [
        {**base, "id": "good", "bot": "lit", "kind": "lit_tilt", "rule": [{"feature": "rr", "op": ">=", "value": 5, "mult": 1.25}]},
        {**base, "id": "meh", "bot": "atlas", "kind": "atlas_tilt", "title": "ATLAS: meh", "rule": [{"feature": "hour", "op": "==", "value": 10, "mult": 0.5}]},
        {**base, "id": "park", "bot": "kalshi", "kind": "parked", "parked_why": "not built"},
        {**base, "id": "old", "bot": "lit", "kind": "lit_tilt", "rule": [{"feature": "vix", "op": ">", "value": 20, "mult": 1.25}]}],
        "rejected_forever": [{"id": "old", "title": "old one", "source": "doc"}]}, open(p, "w"))
    return p


def fake_runner(e, C, rules):
    if e["id"].startswith("good"):
        D = [{"day": "2026-02-02", "usd": 100.0}] * 8 + [{"day": "2026-08-03", "usd": 90.0}] * 6 + \
            [{"day": "2026-11-25", "usd": 20.0}, {"day": "2026-12-08", "usd": 15.0}]
        fl = {h: Z.signflip_p([d["usd"] for d in D if Z.span_of(d["day"], "lit") == h], 2000) for h in ("H1", "H2")}
        return {"proof_ok": True, "why": "better", "deltas": D, "flip": fl, "usd_month_by": {"H1": 120, "H2": 80, "2021-25": 3},
                "head": {"H1": {"per_month": 5682}, "H2": {"per_month": 2750}, "2021-25": {"per_month": 28}},
                "base": {"H1": {"per_month": 5562}, "H2": {"per_month": 2670}, "2021-25": {"per_month": 25}}}
    return {"proof_ok": False, "why": "not better in Jan-Jun (pick)", "deltas": [], "flip": {}, "usd_month_by": {}}


def t_run(tmp):
    reg, od = _reg(tmp), os.path.join(tmp, "out")
    page = os.path.join(tmp, "lab.json")
    board, push = [], []
    emit = lambda k, a, t, d=None: (board.append((k, t)), {"ok": 1})[1]                 # noqa: E731
    pf = lambda t, title="": (push.append((title, t)), (True, "ok"))[1]                    # noqa: E731
    kw = dict(out_dir=od, registry=reg, runner=fake_runner, page_path=page, emit_fn=emit, push_fn=pf, say=lambda *_: None, C=object())
    S = Z.run(data_day="2026-11-18", do_notify=True, edge_path=_edge(tmp, "GREEN"), **kw)
    st = {r["id"]: r["status"] for r in S["rows"]}
    check("run: good -> shadow, meh -> rejected, parked, old blocked", st.get("good") == "shadow" and st.get("meh") == "rejected" and
          st.get("park") == "parked" and st.get("old") == "blocked", st)
    check("run: the cross copy of 'good' on ATLAS exists (rr maps)", "good__on_atlas" in st, st)
    check("run: no cross copy of a rejected-forever idea", "old__on_atlas" not in st, st)
    check("run: blocked ones never reach the runner", not any(r.get("tested") for r in S["rows"] if r["status"] == "blocked"))
    check("run: no board / push without a new READY or RED", not board and not push, (board, push))
    check("run: page written with rows + how + forever", os.path.isfile(page) and json.load(open(page))["rows"] and json.load(open(page))["how"])
    check("run: cells and p needed reported", S["cells"] == 3 and S["p_needed"] == round(0.2 / 3, 5), (S["cells"], S["p_needed"]))
    Z.run(data_day="2026-12-17", do_notify=True, edge_path=_edge(tmp, "GREEN"), **kw)
    S3 = Z.run(data_day="2026-12-18", do_notify=True, edge_path=_edge(tmp, "GREEN"), **kw)
    g = next(r for r in S3["rows"] if r["id"] == "good")
    check("4 weeks later -> READY", g["status"] == "ready", g)
    ready_push = [t for _, t in push if "Reply yes to adopt" in t]
    check("ONE push 'ZEUS Lab: X passed. Reply yes to adopt' per new READY (not again)", len(ready_push) == 2 and all(t.startswith("ZEUS Lab: ") for t in ready_push),
          push)                                                        # good + its ATLAS cross copy (same fake result)
    check("board line kind claude_note for READY", any(k == "claude_note" and "passed" in t for k, t in board), board)
    n0 = len(push)
    Z.run(data_day="2026-12-19", do_notify=True, edge_path=_edge(tmp, "RED"), **kw)
    check("RED light -> one safety push + board line", len(push) == n0 + 1 and "size" in push[-1][1], push[-1:])
    Z.run(data_day="2026-12-20", do_notify=True, edge_path=_edge(tmp, "RED"), **kw)
    check("RED again -> not repeated", len(push) == n0 + 1)
    od2 = os.path.join(tmp, "out2")
    push2 = []
    pf2 = lambda t, title="": (push2.append(t), (True, "ok"))[1]                          # noqa: E731
    Z.run(data_day="2026-11-18", do_notify=False, edge_path=_edge(tmp, "RED"), **{**kw, "out_dir": od2, "push_fn": pf2})
    check("on demand (no --notify): nothing sent", not push2)
    import engine.learn_loop as LL
    real = LL.protected_hashes
    calls = {"n": 0}

    def moving(root=ROOT):
        calls["n"] += 1
        return {"x": calls["n"]}
    LL.protected_hashes = moving
    try:
        od3 = os.path.join(tmp, "out3")
        push3 = []
        pf3 = lambda t, title="": (push3.append(t), (True, "ok"))[1]                      # noqa: E731
        S4 = Z.run(data_day="2026-11-18", do_notify=True, edge_path=_edge(tmp, "RED"), **{**kw, "out_dir": od3, "push_fn": pf3})
        check("a live file moved during the run -> nothing sent, flagged", not push3 and not S4["protected_ok"] and S4["errors"])
    finally:
        LL.protected_hashes = real
    row = next(r for r in S3["rows"] if r["id"] == "good")
    check("page row: $ a month today vs with it, H1 / H2 / 2021-25", row["months"]["H1"] == {"exp": 5682, "now": 5562} and "2021-25" in row["months"], row.get("months"))
    check("ready line has $ both halves", "+$120 / +$80" in Z.ready_line(row), Z.ready_line(row))


def t_proposals(tmp):
    q = os.path.join(tmp, "zq.jsonl")
    with open(q, "w") as fh:
        fh.write(json.dumps({"id": "p1-2026-W47", "day": "2026-11-18", "bot": "atlas", "what": "ATLAS idle 6 sessions while the backtest traded", "evidence": {"n": 6}}) + "\n")
        fh.write("not json\n")
        fh.write(json.dumps({"id": "p2", "bot": "lit", "what": "done one", "status": "tested"}) + "\n")
        fh.write(json.dumps({"id": "atlas_skip_vix15", "bot": "atlas", "what": "dupe of a registry id"}) + "\n")
    R = Z.bot_proposals(q, have={"atlas_skip_vix15"})
    check("bot proposals: new ones shown as proposed, tested / dupes / bad lines skipped", [r["id"] for r in R] == ["p1-2026-W47"] and R[0]["status"] == "proposed", R)
    check("bot proposals: never runnable (no rule, no money)", "months" not in R[0] and R[0]["origin"] == "bot")
    check("bot proposals: missing queue -> none", Z.bot_proposals(os.path.join(tmp, "none.jsonl")) == [])


def t_static():
    src = open(os.path.join(ROOT, "tools", "zeus_lab.py"), encoding="utf-8").read()
    code = re.sub(r'"""[\s\S]*?"""', "", src)
    check("never opens a live file for writing", not re.search(r"open\([^)]*live_model|second_model\.json\"[^)]*\"w|account_b\.json\"[^)]*\"w", code))
    check("no broker / order import", not re.search(r"import .*(ninjatrader|engine\.live\b|botctl|order)|from engine import (live|ninjatrader|botctl)", code))
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("machine-local outputs gitignored", "research/lab/zeus_lab/out/" in gi and "tools/web_public/business/lab_pc.json" in gi)
    js = open(os.path.join(ROOT, "tools", "web_public", "business", "lab.js"), encoding="utf-8").read()
    check("page draws text only (no innerHTML)", "innerHTML" not in js and "insertAdjacentHTML" not in js)
    check("page reads the PC copy first, then the published copy", js.index("lab_pc.json") < js.index("'lab.json'"))
    pub = os.path.join(ROOT, "tools", "web_public", "business", "lab.json")
    P = json.load(open(pub, encoding="utf-8"))
    check("published lab.json has the seeded rows + safety", len(P.get("rows") or []) >= 10 and P.get("safety"))
    check("published lab.json carries no per-trade ledger (small, private-safe)", "deltas" not in json.dumps(P) and os.path.getsize(pub) < 200_000)
    ll = open(os.path.join(ROOT, "engine", "learn_loop.py"), encoding="utf-8").read()
    check("learn loop's nightly run calls the Lab (real runs only)", "zeus_lab.nightly(C)" in ll and "runners is None" in ll)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="zlab_")
    try:
        t_registry()
        t_placebo()
        t_step()
        t_safety(tmp)
        t_run(tmp)
        t_proposals(tmp)
        t_static()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"\nzeus_lab: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
