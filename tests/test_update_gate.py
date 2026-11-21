"""tools/update_gate.py (day-speed 2026-11-20): the update gate's verdicts, its session picker and one real replay.
    python -X utf8 -m tests.test_update_gate [--quick]      (--quick skips d., the real two-worktree replay, ~3 min)
a. compare + verdict: identical -> SAME; a route-time-only change -> SAME; a size change without a model file -> HOLD;
   the same with live_model.json changed -> EXPLAINED; an extra ATLAS entry -> HOLD; the same entry / exit sent twice -> HOLD;
   a candidate that raises -> ERROR
b. model / sizing files are recognised (live_model*.json, second_model.json, accounts/*.json, engine/sizing.py), code is not
c. last_sessions: weekdays with bars 01:30-12:00 ET only (weekend / evening-only days skipped), the newest n
d. HEAD vs HEAD through two real worktrees, 1 session, 60 polls: SAME, exit 0, worktrees removed
"""
from __future__ import annotations

import copy
import datetime as dt
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import update_gate as G  # noqa: E402

FAIL = []


def check(name, ok, info=""):
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAIL.append(name)


def res(lit=None, atlas=None, states=("a", "b"), errors=0):
    return {"ledger": lit or [], "ledger_atlas": atlas or [], "rows": [{"state": s} for s in states], "n_errors": errors}


def main(argv=None):
    quick = "--quick" in (argv or sys.argv[1:])
    e = {"side": "buy", "qty": 5, "stop": 27735.25, "target": 28174.0, "entry_t": 1794827760, "pnl": None, "t": 1794827762, "reason": None}
    x = {"side": "exit", "qty": 5, "stop": None, "target": None, "entry_t": 1794827760, "pnl": -647.0, "t": 1794830402, "reason": "STOP"}
    a1 = {"side": "sell", "qty": 2, "stop": 27432.75, "target": 26918.75, "entry_t": 1794921600, "pnl": None, "t": 1794921602, "reason": None}
    base = res([e, x], [a1])
    c = G.compare(base, copy.deepcopy(base))
    v = G.verdict(c, [])
    check("a. identical -> SAME, exit 0", v[0] == "SAME" and v[1] == 0 and not c["trades"], str(v))
    late = copy.deepcopy(base); late["ledger"][0]["t"] += 2
    check("a. only the route second moved (a speed change) -> SAME", G.verdict(G.compare(base, late), [])[0] == "SAME")
    big = copy.deepcopy(base); big["ledger"][0]["qty"] = 6; big["ledger"][1]["qty"] = 6
    cb = G.compare(base, big)
    vb = G.verdict(cb, [])
    check("a. 5 -> 6 micros with no model file changed -> HOLD, exit 2", vb[0] == "HOLD" and vb[1] == 2 and len(cb["trades"]) == 2,
          str(vb) + str(cb["trades"]))
    check("a. the difference names the entry time and the field", "2026-11-16 06:16 ET" == cb["trades"][0]["entry"]
          and "qty 5 -> 6" in cb["trades"][0]["what"], str(cb["trades"][0]))
    ve = G.verdict(cb, G.model_files_changed(["engine/live.py", "live_model.json"]))
    check("a. the same with live_model.json changed -> EXPLAINED, exit 0", ve[0] == "EXPLAINED" and ve[1] == 0, str(ve))
    extra = copy.deepcopy(base); extra["ledger_atlas"].append({**a1, "entry_t": 1794995400})
    ce = G.compare(base, extra)
    check("a. an extra ATLAS entry -> HOLD ('only in candidate')", G.verdict(ce, [])[0] == "HOLD"
          and ce["trades"][0]["what"] == "only in candidate" and ce["trades"][0]["book"] == "ATLAS", str(ce["trades"]))
    twice = res([e, x, copy.deepcopy(e), copy.deepcopy(x)], [a1])         # redteam 2026-11-21: the same entry + exit sent twice
    ct = G.compare(base, twice)
    vt = G.verdict(ct, [])
    check("a. the candidate sends the same entry and exit TWICE (double orders) -> HOLD, the 2nd ones 'only in candidate'",
          vt[0] == "HOLD" and len(ct["trades"]) == 2 and all(d["what"] == "only in candidate" for d in ct["trades"])
          and {d["kind"] for d in ct["trades"]} == {"entry #2", "exit #2"}, str(vt) + str(ct["trades"]))
    check("a. ... and a doubled base against a single candidate -> HOLD too ('only in base')",
          G.verdict(G.compare(twice, base), [])[0] == "HOLD")
    boom = res([e, x], [a1], errors=5)
    check("a. the candidate's poll raises -> ERROR, exit 1", G.verdict(G.compare(base, boom), [])[:2] == ("ERROR", 1))
    st = res([e, x], [a1], states=("a", "c"))
    vs = G.verdict(G.compare(base, st), [])
    check("a. LIT state differs but no trade -> SAME with the state count named", vs[0] == "SAME" and "1 polls" in vs[2], str(vs))
    mf = G.model_files_changed(["live_model.json", "live_model_lit.json", "second_model.json", "accounts/zlarior.json",
                                "engine/sizing.py", "engine/live.py", "engine/lit.py", "tools/x.py", "data/NQ_1m.csv"])
    check("b. model / sizing files recognised, code and data are not",
          mf == ["accounts/zlarior.json", "engine/sizing.py", "live_model.json", "live_model_lit.json", "second_model.json"], str(mf))
    ET = G.ET
    ts = []
    for day in ("2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16", "2026-11-17", "2026-11-18"):
        d0 = dt.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=ET)
        ts += [int((d0 + dt.timedelta(hours=h)).timestamp()) for h in (3, 10)]
    ts.append(int(dt.datetime(2026, 11, 19, 20, 0, tzinfo=ET).timestamp()))     # an evening-only bar: not a session yet
    got = G.last_sessions(ts, 3)
    check("c. last 3 sessions: weekend and evening-only days skipped", got == ["2026-11-16", "2026-11-17", "2026-11-18"], str(got))
    check("c. all sessions, Friday kept, Saturday / Sunday out", G.last_sessions(ts, 0) == ["2026-11-13", "2026-11-16", "2026-11-17", "2026-11-18"])
    if quick:
        print("  (d. skipped: --quick)")
    else:
        before = subprocess.run(["git", "worktree", "list"], cwd=ROOT, capture_output=True, text=True).stdout
        r = G.run_gate("HEAD", "HEAD", days=["2026-11-16"], max_polls=60)
        after = subprocess.run(["git", "worktree", "list"], cwd=ROOT, capture_output=True, text=True).stdout
        check(f"d. HEAD vs HEAD through two real worktrees, 60 polls: SAME ({r.get('why')})",
              r.get("verdict") == "SAME" and r.get("exit") == 0 and r.get("polls") == 60, str(r)[:400])
        check("d. scratch worktrees removed", before == after, after)
    print(f"\n{'ALL OK' if not FAIL else 'FAILED: ' + ', '.join(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
