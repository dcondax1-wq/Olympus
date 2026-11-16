"""Payout plan (team E, 2026-11-16): tools/money/payout_plan.py -> research/lab/payout_plan.json -> the Business page.

    python -X utf8 -m tests.test_payout_plan       (~20 s; reads the stored files, writes nothing in the repo)

Checks: the tool's selftest (the real eval state, buys only from payouts, at most 4 copies, the calendar); the stored plan
(H1 / H2 / REF, 2 / 3 / 4 / 6 accounts, worst month = fees only, no account id); biz_publish's prop block: the PC's own
business.json gets the eval state + dates, the committed public fixture only the research table; businesscore.cleanProp in
node drops junk; business.json is a private name the public build removes.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))

import biz_publish as BP  # noqa: E402
import payout_plan as PP  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


def main() -> int:
    check("tool selftest", PP.selftest() == 0)
    d = json.load(open(PP.OUT, encoding="utf-8"))
    check("stored plan: H1 / H2 / REF, each with 2 / 3 / 4 / 6 accounts and Zlarior's pass / first payout",
          set(d["spans"]) == {"H1", "H2", "REF"} and all(set(r["plans"]) == {"2", "3", "4", "6"} and r.get("zlarior") for r in d["spans"].values()))
    h2 = d["spans"]["H2"]["plans"]
    check("more accounts = more $ a month on H2 (2 < 3 < 4 < 6), and the 6-account plan buys #3..#6",
          h2["2"]["usd_month_y1"] < h2["3"]["usd_month_y1"] < h2["4"]["usd_month_y1"] < h2["6"]["usd_month_y1"]
          and set(h2["6"]["buy"]) == {"#3", "#4", "#5", "#6"}, {k: v["usd_month_y1"] for k, v in h2.items()})
    check("worst month is fees only (a loss never bigger than the evals bought: >= -6 x $134.40 - $91.80 x 2 - $43)",
          all(p["month_worst"] >= -(6 * 134.40 + 2 * 91.80 + 43.0) - 1 for r in d["spans"].values() for p in r["plans"].values()))
    check("the owner's pocket: never more than the stop rule's 2 re-buys ($183.60)",
          all(p["pocket_max"] <= PP.POCKET_CAP + 0.01 for r in d["spans"].values() for p in r["plans"].values()))
    txt = json.dumps(d)
    check("no account id / Name in the plan (MFFU / Lucid account numbers, Sim names)", not re.search(r"MFFU[A-Z]{2,}\d{4,}|LUCID-?\d|Sim\d{3}", txt))
    pub, own = BP.prop_plan(sample=True), BP.prop_plan(sample=False)
    check("biz_publish: the public fixture's block = the research table only (no eval state, no dates, no buy schedule)",
          pub and pub["table"] and "state" not in pub and "zlarior" not in pub and "buy" not in pub, pub and list(pub))
    check("biz_publish: the PC's own business.json block = + the eval state, Zlarior's dates, the buy schedule",
          own and own["state"]["zlarior"]["room"] == 1145.0 and own["zlarior"]["pass_median"] and len(own["buy"]) == 4, own and list(own))
    fx = json.load(open(os.path.join(BP.WEB, "fixture.json"), encoding="utf-8"))
    check("the committed fixture.json carries the prop table and no private state", fx.get("prop") and "state" not in fx["prop"]
          and "1145" not in json.dumps(fx["prop"]))
    from tools import site_privacy as SP
    check("business.json is a private name (removed from the public build)", "business.json" in SP.PRIVATE_NAMES)
    js = r"""
import('%s').then((C) => {
  const ok = C.cleanProp({table: [{accounts: 2, usd_month_y1: 1049, month_worst: -227}, {accounts: 'x'}, null], rules: ['a', 3],
    zlarior: {pass_median: '2026-12-08', pass_earliest: '<b>'}, buy: [{n: '#3', median: '2027-02-03'}, {}]});
  const out = {n: ok.table.length, worst: C.signed(ok.table[0].worst), early: ok.zlarior.pass_earliest, buy: ok.buy.length, rules: ok.rules.length,
               none: C.cleanProp({}) === null && C.cleanProp(null) === null, doc: C.clean({kind: 'business', models: []}).prop};
  console.log(JSON.stringify(out));
});
""" % ("file://" + os.path.join(ROOT, "tools", "web_public", "business", "businesscore.js"))
    try:
        r = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, timeout=60)
        o = json.loads(r.stdout.strip() or "{}")
    except Exception as e:                       # noqa: BLE001
        o = {"error": str(e)}
    check("businesscore.cleanProp (node): junk rows / dates dropped, signed $, absent = null",
          o.get("n") == 1 and o.get("worst") == "-$227" and o.get("early") is None and o.get("buy") == 1 and o.get("rules") == 1
          and o.get("none") is True and o.get("doc") is None, o)
    page = open(os.path.join(BP.WEB, "index.html"), encoding="utf-8").read()
    check("the Business page has the prop card (hidden until data) and text only through textContent",
          'id="prop"' in page and "innerHTML" not in open(os.path.join(BP.WEB, "business.js"), encoding="utf-8").read())
    n_fail = RES.count(False)
    print(f"payout_plan: {len(RES) - n_fail}/{len(RES)} " + ("OK" if not n_fail else "FAILED"))
    return 0 if not n_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
