"""Research watch-list: research/backlog.json is complete, BACKLOG.md renders, a crossed lead makes one push per data
version, the Sunday ops hook runs once a week, and the live control scores as itself (no lead crosses by accident).

  python -X utf8 -m tests.test_backlog          # ~15 s (one live replay + 6 lead replays with the LIT cache)
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import ops_checks as O  # noqa: E402
from tools import backlog_recheck as BR  # noqa: E402

R = []


def check(name, ok, info=""):
    R.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{' - ' + str(info) if info else ''}")


def main():
    B = json.load(open(BR.BACKLOG, encoding="utf-8"))
    ids = [x["id"] for x in B["leads"]]
    check("unique lead ids", len(ids) == len(set(ids)), ids)
    check("every lead: title, write-up, why, need, kind", all(x.get("title") and os.path.exists(os.path.join(ROOT, "research", "writeups", x["writeup"]))
          and x.get("why_wait") and (x.get("need") or {}).get("n") is not None and x.get("kind") in ("auto", "manual") for x in B["leads"]))
    check("auto leads say what changes; manual leads say how to rerun",
          all((x.get("params") or x.get("post") or x.get("sizing")) for x in B["leads"] if x["kind"] == "auto")
          and all(x.get("rerun") for x in B["leads"] if x["kind"] == "manual"))
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    check("no auto lead is already the live setting", all(any(lm["lit"].get(k) != v for k, v in (x.get("params") or {}).items())
          for x in B["leads"] if x.get("params")))
    res = BR.score_all(log=lambda *_: None)
    check("every auto lead scored", all(i in res["leads"] and "error" not in res["leads"][i] for i in ids
                                        if next(x for x in B["leads"] if x["id"] == i)["kind"] == "auto"),
          {k: v.get("error") for k, v in res["leads"].items() if v.get("error")})
    check("live control = run lit_live (H1 +33,891 / H2 +9,493)", res["live"]["lit"]["H1"]["net"] == 33891 and res["live"]["lit"]["H2"]["net"] == 9493,
          (res["live"]["lit"]["H1"]["net"], res["live"]["lit"]["H2"]["net"]))
    md = BR.render(res)
    check("BACKLOG.md: one row and one section per lead", all(md.count(f"(`{i}`)") == 1 for i in ids))
    fake = json.loads(json.dumps(res))
    lid = ids[0]
    fake["leads"][lid] = {**fake["leads"][lid], "crossed": True}
    n1 = BR.notices(fake, 1_800_000_000)
    check("crossed lead -> one notice keyed by lead + data version", len(n1) == 1 and n1[0]["key"] == f"backlog:{lid}:{res['data_key']}", n1[0]["key"] if n1 else None)
    check("notice says it is not switched on", "Not switched on" in n1[0]["body"])
    st = {"sent": {}}
    calls = []
    run = lambda now: calls.append(now) or n1  # noqa: E731
    a = O.backlog_notices(st, time.time(), runner=run)
    b = O.backlog_notices(st, time.time(), runner=run)
    check("ops hook: once per ISO week", len(a) == 1 and b == [] and len(calls) == 1, st.get("backlog_wk"))
    sent = []
    O.send(a[0], st, sender=lambda p: sent.append(p) or {"sent": 1})
    O.send(a[0], st, sender=lambda p: sent.append(p) or {"sent": 1})
    check("the push goes out once", len(sent) == 1)
    check("a failing re-check never raises", O.backlog_notices({"sent": {}}, time.time(), runner=lambda now: 1 / 0) == [])
    print(f"backlog: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAIL'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    sys.exit(main())
